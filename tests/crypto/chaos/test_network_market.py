"""Network chaos, time sync, market freshness."""

from __future__ import annotations

import pytest

from crypto.chaos.market import MarketDataChaos
from crypto.chaos.network import ChaosNetwork, NetworkFault, TimeSync
from crypto.governor.config import GovernorThresholds
from crypto.governor.freshness import MarketDataFreshnessGate


def test_backoff_no_storm() -> None:
    net = ChaosNetwork(fault=NetworkFault.TIMEOUT, max_retries=3, base_backoff_s=0.01)
    with pytest.raises(TimeoutError):
        net.call(lambda: "ok")
    assert net.attempts <= 4  # initial + retries


def test_half_open() -> None:
    net = ChaosNetwork(fault=NetworkFault.HALF_OPEN, max_retries=2, base_backoff_s=0.01)
    assert net.call(lambda: 1) == 1
    with pytest.raises(TimeoutError):
        net.call(lambda: 2)


def test_time_sync_skew() -> None:
    ts = TimeSync()
    ts.calibrate(exchange_server_ms=1_000_000, local_ms=1_000_500)
    assert ts.local_offset_ms == 500
    assert ts.to_exchange(1_000_500) == 1_000_000
    assert ts.reject_stale_timestamp(1_000_000, 1_020_000, max_skew_ms=5000) is True


def test_stale_blocks_proposal() -> None:
    gate = MarketDataFreshnessGate(
        GovernorThresholds(data_stale_seconds=15, data_critical_stale_seconds=60)
    )
    md = MarketDataChaos(last_update_ms=1_000_000)
    assert md.allow_proposal(gate, now_ms=1_001_000) is True
    md.inject_stale()
    assert md.allow_proposal(gate, now_ms=1_100_000) is False
