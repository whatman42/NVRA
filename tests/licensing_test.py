from god.licensing import load_or_create_identity, DeviceLicenseClient, HttpsDeviceLicenseClient, check_device

def test_device_identity_roundtrip(tmp_path):
    p=tmp_path/"device.json"; a=load_or_create_identity(p); b=load_or_create_identity(p)
    assert a == b and a.device_id

def test_unconfigured_license_service_is_explicit_local_only(tmp_path):
    r=check_device("account", tmp_path/"device.json")
    assert r.allowed and r.status == "LOCAL_ONLY"

def test_unconfigured_client_fails_closed_for_remote_actions(tmp_path):
    i=load_or_create_identity(tmp_path/"device.json")
    assert DeviceLicenseClient().check("account", i)["ok"] is False

def test_license_requires_https():
    try: HttpsDeviceLicenseClient("http://example.test")
    except ValueError as exc: assert str(exc)=="license_service_requires_https"
    else: raise AssertionError("HTTP license service must be rejected")
