"""Typed repository / MemoryStore for all domain tables.

Idempotent inserts use INSERT OR IGNORE / ON CONFLICT where appropriate.
Audit log is append-only (no update/delete methods).
"""

from __future__ import annotations

from .repositories_core import _MemoryStoreCore
from .repositories_ext import _MemoryStoreExt


class MemoryStore(_MemoryStoreCore, _MemoryStoreExt):
    """Typed repository / unit-of-work over the persistent memory database."""
    pass
