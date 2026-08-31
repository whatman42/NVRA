"""Bridge unit tests — discovery, protocol, manager, heartbeat, reconciliation.

All runnable on Linux CI with mocks. No real MT4/MT5.
"""

from __future__ import annotations

import pytest

from god.bridge.models import (
    TerminalInstance,
    Platform,
    TerminalStatus,
    BridgeConnectionState,
)
from god.bridge.discovery import TerminalDiscovery
from god.bridge.protocols import (
    BridgeProtocol,
    build_hello,
    build_hello_ack,
    negotiate_version,
    validate_hello_ack,
    PROTOCOL_VERSION,
)
from god.bridge.errors import IncompatibleVersionError, HandshakeError
from god.bridge.manager import BridgeManager
from god.bridge.reconciliation import compare_positions, Reconciler
from god.ipc.models import Message, MessageType
from god.ipc.tcp import TcpTransport

# Reuse EchoPeer from test_ipc
from tests.test_ipc import EchoPeer


# ── Discovery ────────────────────────────────────────────────────────────


def test_discovery_empty_on_linux_default():
    d = TerminalDiscovery(system="Linux")
    # Without mocks, may find nothing — must not raise
    inst = d.discover()
    assert isinstance(inst, list)


def test_discovery_mt5_with_path_probe():
    def probe(p: str) -> bool:
        return p.endswith("terminal64.exe") and "MetaTrader 5" in p

    def expand(p: str) -> str:
        return p.replace("%ProgramFiles%", "C:/Program Files")

    d = TerminalDiscovery(
        system="Windows",
        path_probe=probe,
        expand=expand,
        which=lambda n: None,
        process_scanner=lambda: [],
    )
    found = d.discover_mt5()
    assert len(found) >= 1
    assert all(t.platform == Platform.MT5 for t in found)
    assert found[0].executable_path is not None
    assert found[0].status == TerminalStatus.DISCOVERED


def test_discovery_multiple_instances():
    paths = {
        "C:/MT5_A/terminal64.exe",
        "C:/MT5_B/terminal64.exe",
    }

    def probe(p: str) -> bool:
        return p in paths

    d = TerminalDiscovery(
        system="test",
        path_probe=probe,
        expand=lambda p: p.replace("%ProgramFiles%", "C:"),
        which=lambda n: None,
        process_scanner=lambda: [
            {"name": "terminal64.exe", "pid": 101, "exe": None},
            {"name": "terminal64.exe", "pid": 102, "exe": None},
        ],
    )
    # Override candidates indirectly by expanding known list — use custom candidates via probe only
    # Force via process + path
    found = d.discover_mt5()
    # At least process-based entries
    assert len(found) >= 1


def test_discovery_mt4_and_mt5_separated():
    def probe(p: str) -> bool:
        return "MetaTrader 4" in p or "MetaTrader 5" in p

    d = TerminalDiscovery(
        system="Windows",
        path_probe=probe,
        expand=lambda p: p.replace("%ProgramFiles%", "C:/Program Files").replace(
            "%ProgramFiles(x86)%", "C:/Program Files (x86)"
        ),
        which=lambda n: None,
        process_scanner=lambda: [],
    )
    mt5 = d.discover_mt5()
    mt4 = d.discover_mt4()
    assert all(t.platform == Platform.MT5 for t in mt5)
    assert all(t.platform == Platform.MT4 for t in mt4)


def test_terminal_instance_no_credentials():
    t = TerminalInstance.create(
        platform=Platform.MT5,
        executable_path="/x/terminal64.exe",
        metadata={"note": "test"},
    )
    assert "password" not in t.metadata
    assert "login" not in t.metadata
    assert t.terminal_id


# ── Protocol ─────────────────────────────────────────────────────────────


def test_hello_ack_roundtrip():
    hello = build_hello(platform=Platform.MT5, terminal_id="tid")
    assert hello.message_type == MessageType.HELLO
    assert hello.payload["protocol_version"] == PROTOCOL_VERSION
    ack = build_hello_ack(hello, platform="MT5", terminal_id="tid", instance_id="iid")
    info = validate_hello_ack(ack, hello)
    assert info["accepted"] is True
    assert info["instance_id"] == "iid"


def test_incompatible_version():
    with pytest.raises(IncompatibleVersionError):
        negotiate_version("GOD-BRIDGE/99")


def test_handshake_rejected():
    hello = build_hello()
    ack = build_hello_ack(hello, accepted=False)
    with pytest.raises(HandshakeError):
        validate_hello_ack(ack, hello)


def test_bridge_protocol_helper():
    bp = BridgeProtocol()
    h = bp.hello(platform="MT5")
    assert h.message_type == MessageType.HELLO


# ── Reconciliation ───────────────────────────────────────────────────────


def test_compare_positions_missing():
    brain = [{"position_id": "123", "status": "OPEN"}]
    terminal = []
    discs = compare_positions(brain, terminal)
    assert any(d["type"] == "position_missing_on_terminal" for d in discs)


def test_compare_positions_status_mismatch():
    brain = [{"position_id": "123", "status": "OPEN"}]
    terminal = [{"position_id": "123", "status": "CLOSED"}]
    discs = compare_positions(brain, terminal)
    assert any(d["type"] == "position_status_mismatch" for d in discs)


def test_compare_positions_unexpected():
    brain = []
    terminal = [{"position_id": "999", "status": "OPEN"}]
    discs = compare_positions(brain, terminal)
    assert any(d["type"] == "position_unexpected_on_terminal" for d in discs)


# ── Manager + heartbeat + reconcile over real TCP peer ───────────────────


def test_bridge_manager_full_cycle():
    peer = EchoPeer()
    try:
        transport = TcpTransport(host="127.0.0.1", port=peer.port)
        mgr = BridgeManager(transport)
        health = mgr.connect(timeout=3.0)
        assert health.state == BridgeConnectionState.CONNECTED
        assert health.protocol_version == PROTOCOL_VERSION

        hb = mgr.heartbeat(timeout=2.0)
        assert hb.state in (
            BridgeConnectionState.HEALTHY,
            BridgeConnectionState.CONNECTED,
            BridgeConnectionState.DEGRADED,
        )
        assert hb.missed_heartbeats == 0

        report = mgr.reconcile(brain_positions=[], brain_orders=[])
        assert report.success is True
        assert report.account.get("balance") == 10000.0

        summary = mgr.recover(brain_positions=[])
        assert summary["state"] in (
            BridgeConnectionState.HEALTHY.value,
            BridgeConnectionState.CONNECTED.value,
        )
        mgr.disconnect()
        assert mgr.state == BridgeConnectionState.DISCONNECTED
    finally:
        peer.close()


def test_bridge_manager_incompatible_peer():
    def bad_handler(msg: Message) -> Message:
        return Message.create(
            message_type=MessageType.INCOMPATIBLE_VERSION,
            source="ea",
            destination="brain",
            payload={"error": "need GOD-BRIDGE/99"},
            request_id=msg.request_id,
        )

    peer = EchoPeer(handler=bad_handler)
    try:
        transport = TcpTransport(host="127.0.0.1", port=peer.port)
        mgr = BridgeManager(transport)
        with pytest.raises(IncompatibleVersionError):
            mgr.connect(timeout=2.0)
    finally:
        peer.close()


def test_no_strategy_tokens_in_bridge_source():
    """Intelligence boundary: bridge package must not contain strategy tokens."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "god" / "bridge"
    # Also check ipc
    roots = [
        pathlib.Path(__file__).resolve().parents[1] / "god" / "bridge",
        pathlib.Path(__file__).resolve().parents[1] / "god" / "ipc",
    ]
    forbidden = re.compile(
        r"\b(rsi|macd|adx|bollinger|ichimoku|stochastic|ema_cross|strategy_signal)\b",
        re.I,
    )
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            m = forbidden.search(text)
            assert m is None, f"forbidden token in {path}: {m.group(0)}"
