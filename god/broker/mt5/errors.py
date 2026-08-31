"""MT5 adapter errors — fail closed."""


class MT5AdapterError(Exception):
    """Base adapter error."""


class MT5NotAvailableError(MT5AdapterError):
    """MetaTrader5 package or terminal not available on this host."""


class MT5ReconciliationError(MT5AdapterError):
    """Internal vs broker state mismatch."""


class MT5IdempotencyError(MT5AdapterError):
    """Duplicate client order id blocked."""
