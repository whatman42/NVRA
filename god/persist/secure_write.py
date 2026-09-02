"""Atomic secure file writers with restrictive permissions (0600 / dir 0700)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Union


def secure_write_text(path: Union[str, Path], data: str) -> None:
    """Atomically write text to *path* with mode 0o600; parent dir 0o700 when possible."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        fd = -1
    finally:
        if fd != -1:
            os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def secure_write_json(
    path: Union[str, Path],
    data: Any,
    *,
    indent: int = 2,
) -> None:
    """Serialize *data* as JSON and write via :func:`secure_write_text`."""
    secure_write_text(path, json.dumps(data, indent=indent))
