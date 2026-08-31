from god.cloud.google_drive import SecureBackup

def test_secure_backup_roundtrip(tmp_path):
    src=tmp_path/"a.bin"; enc=tmp_path/"a.nvra"; out=tmp_path/"b.bin"
    src.write_bytes(b"NVRA state")
    SecureBackup(SecureBackup.generate_key()).encrypt_file(src, enc)
    # same key is needed; generate once for a real roundtrip
    key=SecureBackup.generate_key(); SecureBackup(key).encrypt_file(src,enc); SecureBackup(key).decrypt_file(enc,out)
    assert out.read_bytes()==src.read_bytes()
