"""IPC unit tests — fully runnable on Linux CI (no Windows / MT required)."""

from __future__ import annotations

import json
import socket
import struct
import threading
import time

import pytest

from god.ipc.models import Message, MessageType, PROTOCOL_VERSION, ConnectionState
from god.ipc.tcp import TcpTransport
from god.ipc.errors import TimeoutError, ConnectionError, ProtocolError


def _frame(msg: Message) -> bytes:
    raw = msg.to_json().encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


class EchoPeer:
    """Minimal length-prefixed JSON echo / protocol peer for tests.

    Survives client disconnect/reconnect cycles on Windows (WinError 10053
    ConnectionAbortedError) so BridgeManager.recover() can handshake again.
    """

    def __init__(self, handler=None):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(5)
        self.port = self._server.getsockname()[1]
        self._handler = handler or self._default_handler
        self._thread = threading.Thread(target=self._serve, daemon=True, name="EchoPeer")
        self._stop = False
        self._thread.start()

    def _default_handler(self, msg: Message) -> Message | None:
        if msg.message_type == MessageType.HELLO:
            return Message.create(
                message_type=MessageType.HELLO_ACK,
                source="ea",
                destination="brain",
                payload={
                    "protocol_version": PROTOCOL_VERSION,
                    "bridge_version": "test",
                    "accepted": True,
                    "platform": "MT5",
                    "terminal_id": "t1",
                    "instance_id": "i1",
                    "nonce": msg.payload.get("nonce"),
                },
                request_id=msg.request_id,
                correlation_id=msg.request_id,
            )
        if msg.message_type == MessageType.HEARTBEAT:
            return Message.create(
                message_type=MessageType.HEARTBEAT_ACK,
                source="ea",
                destination="brain",
                payload={"echo": msg.payload.get("t")},
                request_id=msg.request_id,
                correlation_id=msg.request_id,
            )
        if msg.message_type == MessageType.RECONCILE_REQUEST:
            return Message.create(
                message_type=MessageType.RECONCILE_RESPONSE,
                source="ea",
                destination="brain",
                payload={
                    "account": {"balance": 10000.0, "equity": 10000.0},
                    "positions": [],
                    "orders": [],
                },
                request_id=msg.request_id,
                correlation_id=msg.request_id,
            )
        return Message.create(
            message_type=MessageType.ERROR,
            source="ea",
            destination="brain",
            payload={"error": "unhandled"},
            request_id=msg.request_id,
            correlation_id=msg.request_id,
        )

    def _serve(self):
        self._server.settimeout(0.5)
        while not self._stop:
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(2.0)
            buf = b""
            try:
                while not self._stop:
                    try:
                        chunk = conn.recv(65536)
                    except socket.timeout:
                        continue
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        # Windows: client shutdown/close surfaces as WinError 10053
                        # (ConnectionAbortedError). Treat as clean peer close so the
                        # accept loop stays alive for reconnect (e.g. BridgeManager.recover).
                        break
                    if not chunk:
                        break
                    buf += chunk
                    while len(buf) >= 4:
                        (n,) = struct.unpack(">I", buf[:4])
                        if len(buf) < 4 + n:
                            break
                        body = buf[4 : 4 + n]
                        buf = buf[4 + n :]
                        try:
                            msg = Message.from_json(body.decode("utf-8"))
                        except Exception:
                            break
                        resp = self._handler(msg)
                        if resp is not None:
                            try:
                                conn.sendall(_frame(resp))
                            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                                break
            finally:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self):
        self._stop = True
        try:
            self._server.close()
        except OSError:
            pass
        # Give daemon thread a brief chance to exit accept loop
        self._thread.join(timeout=1.0)


def test_message_roundtrip():
    m = Message.create(
        message_type=MessageType.HELLO,
        source="brain",
        destination="ea",
        payload={"nonce": "abc"},
    )
    raw = m.to_json()
    m2 = Message.from_json(raw)
    assert m2.message_type == MessageType.HELLO
    assert m2.payload["nonce"] == "abc"
    assert m2.protocol_version == PROTOCOL_VERSION


def test_message_rejects_unknown_type():
    with pytest.raises(ValueError):
        Message.from_dict({"message_type": "NOT_A_REAL_TYPE", "request_id": "x"})


def test_tcp_connect_hello():
    peer = EchoPeer()
    try:
        t = TcpTransport(host="127.0.0.1", port=peer.port)
        t.connect(timeout=2.0)
        assert t.state == ConnectionState.CONNECTED
        hello = Message.create(
            message_type=MessageType.HELLO,
            source="brain",
            destination="ea",
            payload={"protocol_version": PROTOCOL_VERSION, "nonce": "n1"},
        )
        ack = t.request(hello, timeout=3.0)
        assert ack.message_type == MessageType.HELLO_ACK
        assert ack.payload.get("accepted") is True
        t.disconnect()
        assert t.state == ConnectionState.DISCONNECTED
    finally:
        peer.close()


def test_tcp_timeout():
    peer = EchoPeer(handler=lambda m: None)  # never replies
    try:
        t = TcpTransport(host="127.0.0.1", port=peer.port)
        t.connect(timeout=2.0)
        msg = Message.create(
            message_type=MessageType.HEARTBEAT,
            source="brain",
            destination="ea",
            payload={},
        )
        with pytest.raises(TimeoutError):
            t.request(msg, timeout=0.4)
        t.disconnect()
    finally:
        peer.close()


def test_tcp_health():
    peer = EchoPeer()
    try:
        t = TcpTransport(host="127.0.0.1", port=peer.port)
        t.connect()
        h = t.health()
        assert h["state"] == ConnectionState.CONNECTED.value
        assert h["port"] == peer.port
        t.disconnect()
    finally:
        peer.close()


def test_tcp_reconnect_after_disconnect():
    """Client disconnect then reconnect must succeed (Windows recover path)."""
    peer = EchoPeer()
    try:
        t = TcpTransport(host="127.0.0.1", port=peer.port)
        t.connect(timeout=2.0)
        hello = Message.create(
            message_type=MessageType.HELLO,
            source="brain",
            destination="ea",
            payload={"protocol_version": PROTOCOL_VERSION, "nonce": "n1"},
        )
        ack = t.request(hello, timeout=3.0)
        assert ack.message_type == MessageType.HELLO_ACK
        t.disconnect()
        assert t.state == ConnectionState.DISCONNECTED

        # Second cycle — peer must still be accepting (server thread alive)
        t.connect(timeout=2.0)
        hello2 = Message.create(
            message_type=MessageType.HELLO,
            source="brain",
            destination="ea",
            payload={"protocol_version": PROTOCOL_VERSION, "nonce": "n2"},
        )
        ack2 = t.request(hello2, timeout=3.0)
        assert ack2.message_type == MessageType.HELLO_ACK
        assert ack2.payload.get("accepted") is True
        t.disconnect()
    finally:
        peer.close()


def test_malformed_frame_protocol_error():
    # Direct socket pair to inject bad frame
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def bad_peer():
        conn, _ = srv.accept()
        # length says 5 bytes but body is not valid json
        conn.sendall(struct.pack(">I", 5) + b"xxxxx")
        time.sleep(0.2)
        conn.close()

    threading.Thread(target=bad_peer, daemon=True).start()
    t = TcpTransport(host="127.0.0.1", port=port)
    t.connect(timeout=2.0)
    with pytest.raises(ProtocolError):
        t.receive(timeout=2.0)
    t.disconnect()
    srv.close()
