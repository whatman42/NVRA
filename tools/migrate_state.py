"""CLI for portable NVRA state/model migration."""
from __future__ import annotations
import argparse
from pathlib import Path
from god.persist.migration import create_migration_bundle, inspect_migration_bundle, restore_migration_bundle


def main() -> int:
    p = argparse.ArgumentParser(prog="nvra-migrate")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--data-root", required=True)
    e.add_argument("--model-root")
    e.add_argument("--config")
    e.add_argument("--output", required=True)
    e.add_argument("--version", default="")
    i = sub.add_parser("inspect")
    i.add_argument("bundle")
    r = sub.add_parser("import")
    r.add_argument("bundle")
    r.add_argument("--data-root", required=True)
    r.add_argument("--replace", action="store_true")
    a = p.parse_args()
    if a.cmd == "export":
        extra = {}
        if a.model_root:
            model_root = Path(a.model_root).expanduser()
            if model_root.exists():
                # Preserve the model registry tree without merging it into runtime state.
                for path in model_root.rglob("*"):
                    if path.is_file():
                        rel = path.relative_to(model_root).as_posix()
                        extra[f"models/{rel}"] = path
        if a.config:
            extra["config/settings.yaml"] = Path(a.config)
        m = create_migration_bundle(a.output, data_root=a.data_root, extra_paths=extra, source_version=a.version)
    elif a.cmd == "inspect":
        m = inspect_migration_bundle(a.bundle)
    else:
        m = restore_migration_bundle(a.bundle, data_root=a.data_root, replace=a.replace)
    print({"ok": True, "schema": m.schema_version, "files": len(m.files), "source_version": m.source_version})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
