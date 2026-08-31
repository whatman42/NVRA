"""Deterministic source audit for NVRA Unified.

Checks every Python source line through AST parsing, duplicate function bodies,
unreachable statements, dependency declarations, import graph reachability,
workflow/build consistency, live-order surfaces, and repository hygiene.
It is intentionally static: it never connects to a broker or market.
"""
from __future__ import annotations
import ast, hashlib, json, pathlib, re, sys
from collections import defaultdict, deque

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_ROOTS = [ROOT / "god", ROOT / "src", ROOT / "nvra_unified"]
PY_FILES = sorted(p for r in SOURCE_ROOTS if r.exists() for p in r.rglob("*.py") if "__pycache__" not in p.parts)
EXTERNAL = {"numpy":"numpy","sklearn":"scikit-learn","lightgbm":"lightgbm","xgboost":"xgboost","catboost":"catboost","torch":"torch","shap":"shap","PySide6":"PySide6","psutil":"psutil","requests":"requests","httpx":"httpx","urllib3":"urllib3","ccxt":"ccxt","keyring":"keyring","MetaTrader5":"MetaTrader5","yaml":"PyYAML","pytest":"pytest","google_auth_oauthlib":"google-auth-oauthlib","googleapiclient":"google-api-python-client","google":"google-auth"}
REQ = (ROOT / "requirements.txt").read_text(encoding="utf-8") if (ROOT/"requirements.txt").exists() else ""
req_names = set()
for line in REQ.splitlines():
    if line.lstrip().startswith("#"):
        continue
    m = re.match(r"\s*([A-Za-z0-9_.-]+)(?:[<>=!~]|;|$)", line)
    if m: req_names.add(m.group(1).lower())

issues=[]; syntax=[]; duplicate_bodies=[]; unreachable=[]; imports=defaultdict(set); module_defs={}; line_count=0

def norm_body(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), annotate_fields=False, include_attributes=False)

body_hashes=defaultdict(list)
for p in PY_FILES:
    rel=str(p.relative_to(ROOT)); text=p.read_text(encoding="utf-8", errors="strict"); line_count += len(text.splitlines())
    try: tree=ast.parse(text, filename=rel)
    except Exception as e: syntax.append((rel, str(e))); continue
    module_defs[rel]=tree
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            # Preserve full module paths; collapsing to top-level names created
            # thousands of false orphan reports in nested packages.
            imports[rel].update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            module = n.module or ""
            if n.level:
                # Resolve relative imports against the importing module package.
                src_mod = rel[:-3].replace("/", ".")
                package = src_mod.rsplit(".", 1)[0] if "." in src_mod else ""
                parts = package.split(".") if package else []
                trim = max(0, n.level - 1)
                base = parts[:max(0, len(parts) - trim)]
                resolved = ".".join([*base, module] if module else base)
                if resolved:
                    imports[rel].add(resolved)
            elif module:
                imports[rel].add(module)
        if isinstance(n,(ast.FunctionDef, ast.AsyncFunctionDef)) and len(n.body) >= 3:
            h=hashlib.sha256(norm_body(n.body).encode()).hexdigest()
            body_hashes[h].append((rel,n.name,n.lineno,len(n.body)))
    # Simple unreachable-code detector in every statement list.
    def scan(seq, where):
        terminated=False
        for node in seq:
            if terminated:
                unreachable.append((rel, getattr(node,'lineno',0), where, type(node).__name__))
            if isinstance(node,(ast.Return,ast.Raise,ast.Break,ast.Continue)):
                terminated=True
            for child_name, child in ast.iter_fields(node):
                if isinstance(child,list) and child and all(isinstance(x,ast.stmt) for x in child): scan(child, f"{where}.{child_name}")
                elif isinstance(child,ast.AST) and isinstance(child,(ast.If,ast.For,ast.While,ast.Try,ast.With,ast.AsyncWith)):
                    pass
    scan(tree.body,"module")

duplicate_bodies=[v for v in body_hashes.values() if len(v)>1]
# Ignore trivial wrappers / test fixtures; report meaningful repeated implementations.
duplicate_bodies=[v for v in duplicate_bodies if v[0][3] >= 5]
used_external=sorted({m for vals in imports.values() for m in vals if m in EXTERNAL})
missing=[(m,EXTERNAL[m]) for m in used_external if EXTERNAL[m].lower() not in req_names and not any(x.startswith(EXTERNAL[m].lower()+op) for x in req_names for op in ('>','='))]

# Internal import graph and reachability from product entrypoints.
internal_names={p.relative_to(ROOT).with_suffix("").as_posix().replace('/','.') for p in PY_FILES}
def resolve_import(src, imp):
    if not imp.startswith(('god','src','nvra_unified')): return None
    candidates=[imp]
    if src:
        pkg='.'.join(src.split('.')[:-1])
        if imp.startswith('.'):
            dots=len(imp)-len(imp.lstrip('.')); tail=imp.lstrip('.')
            base=pkg.split('.')[:max(0,len(pkg.split('.'))-dots+1)]
            candidates=['.'.join(base+[tail]) if tail else '.'.join(base)]
    for c in candidates:
        if c in internal_names: return c
        if c+'.__init__' in internal_names: return c+'.__init__'
    return None

graph=defaultdict(set)
for rel, imps in imports.items():
    src=rel[:-3].replace('/','.')
    for imp in imps:
        dst=resolve_import(src,imp)
        if dst: graph[src].add(dst)
entry_modules={'nvra_unified.__main__','god.loop.autonomous','god.app.nung_app','god.runtime.main','god.gui.main','god.nvra_app.main'}
reachable=set(entry_modules); q=deque(entry_modules)
while q:
    x=q.popleft()
    for y in graph.get(x,()):
        if y not in reachable: reachable.add(y); q.append(y)
orphan=sorted(m for m in internal_names if m.split('.')[0] in {'god','src','nvra_unified'} and m not in reachable and not m.endswith('.__init__'))

workflows=list((ROOT/'.github/workflows').glob('*.yml')) if (ROOT/'.github/workflows').exists() else []
workflow_text={p.name:p.read_text(encoding='utf-8',errors='ignore') for p in workflows}
workflow_conflicts=[name for name,t in workflow_text.items() if 'NVRA.exe' in t and 'NVRAFX.exe' not in t]
live_surfaces=[]
for p in PY_FILES:
    text=p.read_text(encoding='utf-8',errors='ignore')
    if re.search(r'\b(create_order|order_send|send_order|_do_create_order)\b',text): live_surfaces.append(str(p.relative_to(ROOT)))

cache=list(ROOT.rglob('*.pyc')) + [p for p in ROOT.rglob('*') if p.is_dir() and p.name in {'__pycache__','.pytest_cache'}]
secrets=[]
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix.lower() in {'.env','.pem','.key'} and '.git' not in p.parts: secrets.append(str(p.relative_to(ROOT)))

report={
 'schema':'nvra-audit-v2','python_files':len(PY_FILES),'source_lines':line_count,
 'syntax_errors':syntax,'missing_requirements':missing,
 'duplicate_function_bodies':duplicate_bodies,'unreachable_statements':unreachable,
 'reachable_modules':len(reachable),'orphan_modules':orphan,
 'workflow_conflicts':workflow_conflicts,'live_execution_surfaces':live_surfaces,
 'generated_artifacts':len(cache),'suspicious_secret_files':secrets,
}
(ROOT/'AUDIT_DEEP_RELEASE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Hard failures: syntax, missing deps, unsafe artifacts. Duplicates/orphans are audit findings and are
# only hard failures when they represent exact non-trivial duplicates or workflow conflicts.
if syntax or missing or cache or workflow_conflicts or duplicate_bodies or secrets:
    issues.extend(['syntax' for _ in syntax]); issues.extend(['dependency' for _ in missing]); issues.extend(['cache']); issues.extend(['workflow' for _ in workflow_conflicts]); issues.extend(['duplicate' for _ in duplicate_bodies]); issues.extend(['secret' for _ in secrets])
print(json.dumps({'status':'PASS' if not issues else 'FAIL','issues':sorted(set(issues)), 'python_files':len(PY_FILES),'source_lines':line_count,'orphan_modules':len(orphan),'duplicate_groups':len(duplicate_bodies)},indent=2))
sys.exit(1 if issues else 0)
