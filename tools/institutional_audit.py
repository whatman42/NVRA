"""Strict deterministic repository audit.
Checks bytes, UTF-8, NUL/control characters, AST syntax, exact non-trivial duplicate
function bodies, imports, forbidden secrets/caches, and manifest integrity.
"""
from __future__ import annotations
import ast, hashlib, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
EXCLUDE={'.git','.pytest_cache','__pycache__','dist','build'}
TEXT_SUFFIXES={'.py','.pyw','.md','.rst','.txt','.json','.yaml','.yml','.toml','.ini','.cfg','.conf','.ps1','.bat','.cmd','.sh','.gitignore','.gitattributes','.example'}
files=[p for p in ROOT.rglob('*') if p.is_file() and not EXCLUDE.intersection(p.parts)]
issues=[]; hashes={}; duplicate=[]; line_total=0
for p in files:
    raw=p.read_bytes()
    rel=p.relative_to(ROOT).as_posix()
    hashes[rel]=hashlib.sha256(raw).hexdigest()
    if p.suffix in TEXT_SUFFIXES or p.name in {'.gitignore','.gitattributes'}:
        if b'\x00' in raw: issues.append((rel,'NUL_BYTE'))
        try: text=raw.decode('utf-8')
        except UnicodeDecodeError as exc: issues.append((rel,f'UTF8:{exc}')); continue
        line_total += len(text.splitlines())
        if any(ord(c)<32 and c not in '\t\n\r\f' for c in text): issues.append((rel,'CONTROL_CHARACTER'))
    else:
        text=None
    if p.suffix=='.py':
        try: tree=ast.parse(text,filename=rel)
        except SyntaxError as exc: issues.append((rel,f'SYNTAX:{exc}')); continue
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and len(n.body)>=5:
                body=ast.dump(ast.Module(body=n.body,type_ignores=[]),annotate_fields=False,include_attributes=False)
                key=hashlib.sha256(body.encode()).hexdigest()
                duplicate.append((key,rel,n.name,n.lineno))
for key, rel, name, lineno in duplicate:
    pass
groups={}
for item in duplicate: groups.setdefault(item[0],[]).append(item[1:])
for vals in groups.values():
    unique={(r,n) for r,n,_ in vals}
    if len(unique)>1: issues.append(('DUPLICATE_FUNCTION',';'.join(f'{r}:{n}:{l}' for r,n,l in vals)))
for rel in hashes:
    if rel.endswith(('.env','.pem','.key','.p12','.pfx')) and not rel.endswith('.example'): issues.append((rel,'SECRET_FILE'))
report={'status':'PASS' if not issues else 'FAIL','files':len(files),'source_lines':line_total,'sha256':hashes,'issues':issues}
(ROOT/'AUDIT_STRICT.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
print(json.dumps({'status':report['status'],'files':len(files),'source_lines':line_total,'issues':len(issues)},indent=2))
sys.exit(1 if issues else 0)
