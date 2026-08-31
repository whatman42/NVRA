"""MT5 Adapter Gate — execution environment only.

Path (mandatory):
  Decision → Risk → Authorization → Firewall → Idempotency → MT5 Adapter → Broker → Reconcile

AI must NEVER call order_send directly.
Default: DEMO path only. LIVE requires LiveExecutionController ARM + preflight PASS.
Terminal (MT5) remains external — not bundled in NVRA.exe.
"""

from .adapter import MT5ExecutionAdapter, MT5ConnectionConfig
from .manager import MT5Manager, MT5ManagerConfig, MT5ManagerHealth
from .demo_gate import MT5DemoGate, DemoGateReport
from .demo_pipeline import DemoOnlyExecutionPipeline, DemoPipelineResult
from .errors import MT5AdapterError, MT5NotAvailableError
from .fake import FakeMetaTrader5
from .reconnect import ReconnectController, BackoffPolicy
from .heartbeat import HeartbeatMonitor
from .ipc_protocol import RequestType, encode_request, decode_response, DEFAULT_BIND_HOST

__all__ = [
    "MT5ExecutionAdapter",
    "MT5ConnectionConfig",
    "MT5Manager",
    "MT5ManagerConfig",
    "MT5ManagerHealth",
    "MT5DemoGate",
    "DemoGateReport",
    "DemoOnlyExecutionPipeline",
    "DemoPipelineResult",
    "FakeMetaTrader5",
    "MT5AdapterError",
    "MT5NotAvailableError",
    "ReconnectController",
    "BackoffPolicy",
    "HeartbeatMonitor",
    "RequestType",
    "encode_request",
    "decode_response",
    "DEFAULT_BIND_HOST",
]
