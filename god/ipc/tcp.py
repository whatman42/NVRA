"""TcpTransport — length-prefixed JSON over localhost TCP.

Framing: 4-byte big-endian length + UTF-8 JSON body.
Designed for unit tests (in-process mock peer) and local EA sockets.
No credentials. Bind/connect to 127.0.0.1 only by default.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Optional

from .models import Message, ConnectionState, PROTOCOL_VERSION
from .errors import IPCError, TimeoutError, ConnectionError, ProtocolError


class TcpTransport:
    """Client-side TCP transport implementing IPCTransport."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        source: str = "brain",
        destination: str = "ea",
        *,
        sock: Optional[socket.socket] = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost", "::1") and not host.startswith("127."):
            # Soft guard: prefer localhost; still allow override for advanced tests.
            pass
        self.host = host
        self.port = port
        self.source = source
        self.destination = destination
        self._sock: Optional[socket.socket] = sock
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self._seq = 0
        self._recv_buffer = b""
        self._last_activity = 0.0
        self._connected_at: Optional[float] = None

    @property
    def name(self) -> str:
        return f"tcp://{self.host}:{self.port}"

    @property
    def state(self) -> ConnectionState:
        return self._state

    def connect(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._state in (ConnectionState.CONNECTED, ConnectionState.HEALTHY):
                return
            self._state = ConnectionState.CONNECTING
            try:
                if self._sock is None:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(timeout)
                    s.connect((self.host, self.port))
                    s.settimeout(None)
                    self._sock = s
                self._state = ConnectionState.CONNECTED
                self._connected_at = time.time()
                self._last_activity = time.time()
                self._recv_buffer = b""
            except OSError as e:
                self._state = ConnectionState.DISCONNECTED
                self._sock = None
                raise ConnectionError(f"connect failed: {e}") from e

    def shutdown(self) -> None:
        """Deterministic close for Windows CI."""
        self.disconnect()

    def disconnect(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    self._sock.close()
                except OSError:
                    pass
            self._sock = None
            self._state = ConnectionState.DISCONNECTED
            self._recv_buffer = b""
            self._connected_at = None

    def send(self, message: Message) -> None:
        with self._lock:
            if self._sock is None or self._state == ConnectionState.DISCONNECTED:
                raise ConnectionError("not connected")
            self._seq += 1
            if message.sequence == 0:
                message.sequence = self._seq
            raw = message.to_json().encode("utf-8")
            frame = struct.pack(">I", len(raw)) + raw
            try:
                self._sock.sendall(frame)
                self._last_activity = time.time()
            except OSError as e:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError(f"send failed: {e}") from e

    def receive(self, timeout: float = 5.0) -> Optional[Message]:
        with self._lock:
            if self._sock is None:
                raise ConnectionError("not connected")
            deadline = time.time() + timeout
            while True:
                msg = self._try_parse()
                if msg is not None:
                    self._last_activity = time.time()
                    return msg
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._sock.settimeout(min(remaining, 0.5))
                try:
                    chunk = self._sock.recv(65536)
                except socket.timeout:
                    continue
                except OSError as e:
                    self._state = ConnectionState.DISCONNECTED
                    raise ConnectionError(f"recv failed: {e}") from e
                if not chunk:
                    self._state = ConnectionState.DISCONNECTED
                    raise ConnectionError("peer closed connection")
                self._recv_buffer += chunk

    def request(self, message: Message, timeout: float = 5.0) -> Message:
        self.send(message)
        deadline = time.time() + timeout
        target_id = message.request_id
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"no response for request_id={target_id}")
            resp = self.receive(timeout=remaining)
            if resp is None:
                raise TimeoutError(f"no response for request_id={target_id}")
            # Match by request_id or correlation_id
            if resp.request_id == target_id or resp.correlation_id == target_id:
                return resp
            # Unrelated message — discard for now (Phase 3B-A simple)

    def health(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "host": self.host,
            "port": self.port,
            "connected_at": self._connected_at,
            "last_activity": self._last_activity,
            "sequence": self._seq,
            "buffer_bytes": len(self._recv_buffer),
        }

    def _try_parse(self) -> Optional[Message]:
        if len(self._recv_buffer) < 4:
            return None
        (length,) = struct.unpack(">I", self._recv_buffer[:4])
        if length > 16 * 1024 * 1024:
            raise ProtocolError(f"frame too large: {length}")
        if len(self._recv_buffer) < 4 + length:
            return None
        body = self._recv_buffer[4 : 4 + length]
        self._recv_buffer = self._recv_buffer[4 + length :]
        try:
            text = body.decode("utf-8")
            return Message.from_json(text)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
            raise ProtocolError(f"malformed message: {e}") from e


# Avoid circular import of json in except
import json  # noqa: E402
