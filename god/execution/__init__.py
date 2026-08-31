"""ExecutionProvider abstraction (Null + Virtual).

Future MT4/MT5 bridges implement the same protocol.
"""

from .protocols import ExecutionProvider
from .null import NullExecutionProvider
from .virtual import VirtualExecutionProvider

__all__ = [
    "ExecutionProvider",
    "NullExecutionProvider",
    "VirtualExecutionProvider",
]
