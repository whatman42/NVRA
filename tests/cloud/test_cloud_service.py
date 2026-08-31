from god.cloud.google_drive import CloudBackupService

class FakeDrive:
    def upload(self, path): return {"name": path.name}
class FakeEncryption:
    def encrypt_file(self, src, dst): dst.write_bytes(src.read_bytes())

def test_cloud_backup_service_exports_and_cleans_plaintext(tmp_path):
    root=tmp_path/"data"; (root/"state").mkdir(parents=True); (root/"state"/"x.json").write_text("{}")
    result=CloudBackupService(FakeDrive(),FakeEncryption()).export_and_upload(tmp_path/"out", data_root=root, source_version="V7.1")
    assert result["manifest"]["source_version"] == "V7.1"
    assert list((tmp_path/"out").iterdir()) == []
