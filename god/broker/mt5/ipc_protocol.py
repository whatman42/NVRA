"""IPC protocol constants inspired by ZeroMQ MT bridges (BonneVoyager-style).

NVRA uses this only as a *message schema* for optional localhost EA bridges.
Default bind: 127.0.0.1 only — never 0.0.0.0 in production NVRA.
Does not open sockets by itself (no side effects on import).
"""

from __future__ import annotations

from enum import IntEnum


class RequestType(IntEnum):
    PING = 1
    TRADE_OPEN = 11
    TRADE_MODIFY = 12
    TRADE_DELETE = 13
    DELETE_ALL_PENDING = 21
    CLOSE_MARKET = 22
    CLOSE_ALL_MARKET = 23
    RATES = 31
    ACCOUNT = 41
    ORDERS = 51
    BARS = 61
    HEARTBEAT = 71


class ResponseStatus(IntEnum):
    OK = 0
    FAILED = 1


DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_REP_PORT = 5555
DEFAULT_PUSH_PORT = 5556


def encode_request(req_id: str, req_type: RequestType, *parts: str) -> str:
    """Pipe-separated protocol: id|type|..."""
    body = [str(req_id), str(int(req_type)), *[str(p) for p in parts]]
    return "|".join(body)


def decode_response(message: str) -> tuple[str, ResponseStatus, list[str]]:
    parts = message.split("|")
    if len(parts) < 2:
        return ("", ResponseStatus.FAILED, [])
    req_id = parts[0]
    status = ResponseStatus(int(parts[1])) if parts[1].isdigit() else ResponseStatus.FAILED
    return req_id, status, parts[2:]
