"""Terminal identity + ambiguity (Linux fixtures)."""

from __future__ import annotations

from god.bridge.models import Platform, TerminalInstance
from god.bridge.windows.identity import IdentityStatus, resolve_identities


def _t(platform, exe, data, experts, tid=None):
    return TerminalInstance.create(
        platform=platform,
        executable_path=exe,
        data_path=data,
        experts_path=experts,
        terminal_id=tid,
    )


def test_unique_single_candidate():
    inst = [_t(Platform.MT5, "/mt5/terminal64.exe", "/mt5", "/mt5/MQL5/Experts")]
    r = resolve_identities(inst)
    assert r.status == IdentityStatus.UNIQUE
    assert r.selected is not None
    assert r.selected.fingerprint


def test_ambiguous_two_mt5():
    inst = [
        _t(Platform.MT5, "/a/terminal64.exe", "/a", "/a/MQL5/Experts", "a"),
        _t(Platform.MT5, "/b/terminal64.exe", "/b", "/b/MQL5/Experts", "b"),
    ]
    r = resolve_identities(inst, platform=Platform.MT5)
    assert r.status == IdentityStatus.AMBIGUOUS
    assert r.selected is None
    assert len(r.candidates) == 2


def test_explicit_id_selects():
    inst = [
        _t(Platform.MT5, "/a/terminal64.exe", "/a", "/a/MQL5/Experts", "id-a"),
        _t(Platform.MT5, "/b/terminal64.exe", "/b", "/b/MQL5/Experts", "id-b"),
    ]
    r = resolve_identities(inst, explicit_id="id-b")
    assert r.status == IdentityStatus.UNIQUE
    assert r.selected is not None
    assert r.selected.identity_id == "id-b"


def test_not_found():
    r = resolve_identities([])
    assert r.status == IdentityStatus.NOT_FOUND


def test_filter_platform():
    inst = [
        _t(Platform.MT4, "/mt4/terminal.exe", "/mt4", "/mt4/MQL4/Experts"),
        _t(Platform.MT5, "/mt5/terminal64.exe", "/mt5", "/mt5/MQL5/Experts"),
    ]
    r = resolve_identities(inst, platform=Platform.MT4)
    assert r.status == IdentityStatus.UNIQUE
    assert r.selected.platform == Platform.MT4
