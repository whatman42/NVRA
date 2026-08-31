"""Phase 6A — deterministic configuration fingerprint. Secrets excluded."""

from __future__ import annotations

from god.research.provenance import content_hash

from .config import ProductionConfig


def configuration_fingerprint(config: ProductionConfig) -> str:
    """
    Hash of safe configuration only.
    Secret values never included (only secret_ref *names* if present).
    """
    payload = config.to_safe_dict()
    # ensure no accidental secret-like keys
    extra = payload.get("extra") or {}
    payload["extra"] = {
        k: v
        for k, v in extra.items()
        if not any(x in k.lower() for x in ("secret", "password", "token", "key", "pat"))
    }
    return content_hash(payload)


def configuration_id(config: ProductionConfig) -> str:
    return "cfg-" + configuration_fingerprint(config)[:24]
