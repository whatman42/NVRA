"""HTTPS transport for the one-active-device license service."""
from __future__ import annotations
import requests
from urllib.parse import urlparse
from .device import DeviceIdentity, DeviceLicenseClient

class HttpsDeviceLicenseClient(DeviceLicenseClient):
    def __init__(self, base_url: str, timeout: float = 10.0):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("license_service_requires_https")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        super().__init__(self._register, self._check, self._revoke)
    def _post(self, path: str, payload: dict) -> dict:
        r = requests.post(f"{self.base_url}/{path.lstrip('/')}", json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("invalid_license_response")
        return data
    def _register(self, account_id: str, identity: dict) -> dict:
        return self._post("v1/devices/register", {"account_id": account_id, "device": identity})
    def _check(self, account_id: str, identity: dict) -> dict:
        return self._post("v1/devices/check", {"account_id": account_id, "device": identity})
    def _revoke(self, account_id: str, device_id: str) -> dict:
        return self._post("v1/devices/revoke", {"account_id": account_id, "device_id": device_id})
