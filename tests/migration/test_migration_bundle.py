from pathlib import Path
import pytest
from god.persist.migration import MigrationError, create_migration_bundle, inspect_migration_bundle, restore_migration_bundle


def test_round_trip_preserves_state_and_models(tmp_path: Path):
    root = tmp_path / "old"
    (root / "state").mkdir(parents=True)
    (root / "models" / "artifacts").mkdir(parents=True)
    (root / "state" / "portfolio.json").write_text('{"equity":123}', encoding="utf-8")
    (root / "state" / "order_journal.jsonl").write_text('{"status":"FILLED"}\n', encoding="utf-8")
    (root / "models" / "artifacts" / "champion.bin").write_bytes(b"model-v1")
    (root / ".env").write_text("SECRET=must-not-export", encoding="utf-8")
    bundle = tmp_path / "migration.nvra.zip"
    manifest = create_migration_bundle(bundle, data_root=root, source_version="v7")
    assert "state/portfolio.json" in manifest.files
    assert "models/artifacts/champion.bin" in manifest.files
    assert ".env" not in manifest.files
    assert inspect_migration_bundle(bundle).files == manifest.files

    new = tmp_path / "new"
    restore_migration_bundle(bundle, data_root=new)
    assert (new / "state/portfolio.json").read_text() == '{"equity":123}'
    assert (new / "models/artifacts/champion.bin").read_bytes() == b"model-v1"


def test_checksum_tamper_is_rejected(tmp_path: Path):
    import zipfile
    root = tmp_path / "old"
    (root / "state").mkdir(parents=True)
    (root / "state" / "x.txt").write_text("abc")
    bundle = tmp_path / "x.zip"
    create_migration_bundle(bundle, data_root=root)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "state/x.txt":
                data = b"tampered"
            dst.writestr(item, data)
    with pytest.raises(MigrationError, match="checksum_mismatch"):
        inspect_migration_bundle(tampered)
