"""Adversarial paper broker and micro-account constraints."""

from __future__ import annotations

from crypto.execution.adversarial import PROFILES, AdversarialPaperBroker


def test_hostile_can_reject_or_partial() -> None:
    br = AdversarialPaperBroker(PROFILES["hostile"])
    outcomes = {"rejected": 0, "partial": 0, "full": 0, "unknown": 0}
    for _ in range(40):
        o = br.create_order("BTC/USDT", "buy", "market", 1.0, mid_price=100.0)
        if o.get("status") == "unknown" or o.get("id") is None:
            outcomes["unknown"] += 1
        elif o.get("status") == "rejected":
            outcomes["rejected"] += 1
        elif o.get("filled", 0) < o.get("amount", 1) - 1e-9:
            outcomes["partial"] += 1
        else:
            outcomes["full"] += 1
    # Hostile profile must not be frictionless all-full
    assert outcomes["full"] < 40


def test_micro_min_notional() -> None:
    br = AdversarialPaperBroker(PROFILES["micro"])
    # amount survives step_size but notional << min_notional
    o = br.create_order("BTC/USDT", "buy", "market", 0.01, mid_price=100.0)
    assert o["status"] == "rejected"
    assert o.get("error") in ("min_notional", "step_size")


def test_fee_and_slippage_applied() -> None:
    br = AdversarialPaperBroker(PROFILES["retail"])
    o = br.create_order("ETH/USDT", "buy", "market", 1.0, mid_price=1000.0)
    assert o["status"] in ("closed", "open")
    assert o["price"] > 1000.0  # buy pays spread+slip
    assert o["fee"]["cost"] > 0


def test_paper_mode_tag() -> None:
    br = AdversarialPaperBroker(PROFILES["ideal"])
    o = br.create_order("X/USDT", "sell", "limit", 1.0, price=10.0, mid_price=10.0)
    assert o.get("mode") == "PAPER"
