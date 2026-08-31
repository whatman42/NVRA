"""High-level encrypted migration backup service for Google Drive."""
from __future__ import annotations
from pathlib import Path
from god.persist.migration import create_migration_bundle
from .backup import GoogleDriveBackup
from .secure_backup import SecureBackup

class CloudBackupService:
    def __init__(self, drive: GoogleDriveBackup, encryption: SecureBackup):
        self.drive = drive
        self.encryption = encryption

    def export_and_upload(self, destination_dir: str | Path, *, data_root: str | Path, source_version: str = "") -> dict:
        destination_dir = Path(destination_dir); destination_dir.mkdir(parents=True, exist_ok=True)
        plain = destination_dir / "NVRA-MIGRATION-V7.nvra.zip"
        encrypted = destination_dir / "NVRA-MIGRATION-V7.nvra.enc"
        manifest = create_migration_bundle(plain, data_root=data_root, source_version=source_version)
        self.encryption.encrypt_file(plain, encrypted)
        result = self.drive.upload(encrypted)
        plain.unlink(missing_ok=True)
        encrypted.unlink(missing_ok=True)
        return {"manifest": manifest.to_dict(), "drive": result}
