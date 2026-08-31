"""MT4 / MT5 terminal adapters — normalize platform differences at the boundary.

Brain remains platform-agnostic. No trading intelligence.
"""

from .base import TerminalAdapter
from .mt4 import MT4Adapter
from .mt5 import MT5Adapter

__all__ = ["TerminalAdapter", "MT4Adapter", "MT5Adapter"]
