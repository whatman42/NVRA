"""Encrypt migration archives before cloud transport.

Fernet provides authenticated encryption. The key must be kept in the local
secure store or supplied explicitly during recovery; it is never uploaded.
"""
from __future__ import annotations
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

class SecureBackup:
    def __init__(self, key: bytes):
        self._fernet = Fernet(key)
    @staticmethod
    def generate_key() -> bytes:
        return Fernet.generate_key()
    def encrypt_file(self, source: str | Path, destination: str | Path) -> Path:
        source, destination = Path(source), Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self._fernet.encrypt(source.read_bytes()))
        return destination
    def decrypt_file(self, source: str | Path, destination: str | Path) -> Path:
        source, destination = Path(source), Path(destination)
        try:
            payload = self._fernet.decrypt(source.read_bytes())
        except InvalidToken as exc:
            raise ValueError("encrypted_backup_integrity_failure") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return destination
