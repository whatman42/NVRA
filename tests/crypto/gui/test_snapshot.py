"""GUI snapshot bus and wizard secret hygiene."""

from __future__ import annotations

from crypto.gui import GuiSnapshot, SnapshotBus, WizardState, pyside6_available


def test_snapshot_debounce() -> None:
    bus = SnapshotBus(min_interval_ms=500)
    bus.publish(GuiSnapshot(equity=1.0))
    s = bus.get()
    assert s.equity == 1.0
    bus.publish(GuiSnapshot(equity=2.0))
    s2 = bus.get()
    assert s2.equity == 2.0


def test_wizard_no_secret_in_repr() -> None:
    w = WizardState()
    w.set_api_key("KEY123")
    w.set_api_secret("SEC456")
    w.set_telegram_token("TOK789")
    r = repr(w)
    assert "KEY123" not in r
    assert "SEC456" not in r
    assert "TOK789" not in r
    secrets = w.take_secrets()
    assert secrets["api_key"] == "KEY123"
    # cleared
    assert w.take_secrets()["api_key"] == ""


def test_pyside_optional() -> None:
    # must not raise whether installed or not
    assert isinstance(pyside6_available(), bool)
