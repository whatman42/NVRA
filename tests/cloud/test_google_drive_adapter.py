from god.cloud.google_drive import GoogleDriveBackup

def test_drive_adapter_does_not_upload_without_file(tmp_path):
    store = lambda: None
    d=GoogleDriveBackup(tmp_path/"client.json", token_store_get=store, token_store_set=lambda _: None)
    try: d.upload(tmp_path/"missing.zip")
    except FileNotFoundError: pass
    else: raise AssertionError("missing backup must fail")
