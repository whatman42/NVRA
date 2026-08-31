#!/usr/bin/env python3
"""Materialize Phase 2 modules from scripts/data/*.b64 (exact tested content, 44/44)."""
import base64, gzip
from pathlib import Path

DATA = Path(__file__).parent / "data"

MANIFEST = {
    'god/memory/models.py': ['god_memory_models_py_00.b64'],
    'god/memory/models_core.py': ['god_memory_models_core_py_00.b64'],
    'god/memory/models_ext.py': ['god_memory_models_ext_py_00.b64'],
    'god/memory/repositories.py': ['god_memory_repositories_py_00.b64', 'god_memory_repositories_py_01.b64'],
    'tests/test_memory.py': ['tests_test_memory_py_00.b64', 'tests_test_memory_py_01.b64'],
}

def main() -> None:
    for path, parts in MANIFEST.items():
        b64 = "".join((DATA / p).read_text() for p in parts)
        data = gzip.decompress(base64.b64decode(b64))
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"wrote {path} ({len(data)} bytes)")

if __name__ == "__main__":
    main()
