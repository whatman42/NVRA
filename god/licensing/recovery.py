"""Account/device replacement helpers."""
from __future__ import annotations
from .device import DeviceLicenseClient

def revoke_old_device(client: DeviceLicenseClient, account_id: str, old_device_id: str) -> dict:
    if not account_id or not old_device_id:
        return {"ok": False, "status": "INVALID_REQUEST"}
    return client.revoke(account_id, old_device_id)
