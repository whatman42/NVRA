"""Resume from checkpoint — fail-closed on hash mismatch."""

from __future__ import annotations

from typing import Any, Optional

from .checkpoint_store import CheckpointStore
from .context_store import ContextStore
from .models.checkpoint import verify_checkpoint
from .models.context import ContextStatus


class RecoveryService:
    def __init__(
        self,
        context_store: ContextStore,
        checkpoint_store: CheckpointStore,
    ) -> None:
        self.contexts = context_store
        self.checkpoints = checkpoint_store

    def resume(self, context_id: str) -> Optional[dict[str, Any]]:
        """
        Load context + latest checkpoint.
        Returns resume plan or marks CORRUPTED if hash fails.
        """
        ctx = self.contexts.get(context_id)
        if ctx is None:
            return None
        cp = None
        if ctx.checkpoint_reference:
            cp = self.checkpoints.get(ctx.checkpoint_reference)
        if cp is None:
            cp = self.checkpoints.latest_for_context(context_id)
        if cp is not None and not verify_checkpoint(cp):
            ctx.status = ContextStatus.CORRUPTED
            self.contexts.save(ctx)
            return {
                "status": "CORRUPTED",
                "reason": "checkpoint_hash_mismatch",
                "context_id": context_id,
            }
        if ctx.status in (ContextStatus.CORRUPTED, ContextStatus.CANCELLED):
            return {"status": ctx.status.value, "context_id": context_id}
        # mark resume path
        if ctx.status in (ContextStatus.PAUSED, ContextStatus.FAILED, ContextStatus.RUNNING):
            try:
                from .models.context import assert_status_transition

                if ctx.status == ContextStatus.PAUSED:
                    assert_status_transition(ctx.status, ContextStatus.RESUME)
                    ctx.status = ContextStatus.RESUME
                    assert_status_transition(ctx.status, ContextStatus.RUNNING)
                    ctx.status = ContextStatus.RUNNING
                    self.contexts.save(ctx)
            except ValueError:
                pass
        return {
            "status": "RESUME",
            "context_id": context_id,
            "completed_nodes": list(ctx.completed_nodes),
            "checkpoint_id": cp.checkpoint_id if cp else None,
            "stage": ctx.current_stage.value,
        }
