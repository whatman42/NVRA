"""Configurable/injected universe — no hardcoded permanent market truth."""

from __future__ import annotations

from typing import Iterable, Optional

from .models import InstrumentRef, InstrumentStatus


class Universe:
    """Injected instrument set. Empty universe is valid → NO_VALID_CANDIDATE path."""

    def __init__(self, instruments: Optional[Iterable[InstrumentRef | str]] = None) -> None:
        self._items: dict[str, InstrumentRef] = {}
        self._status: dict[str, InstrumentStatus] = {}
        if instruments:
            for item in instruments:
                self.add(item)

    def add(self, item: InstrumentRef | str, *, asset_class: str = "UNKNOWN") -> None:
        if isinstance(item, str):
            sym = item.strip().upper()
            if not sym:
                return
            ref = InstrumentRef(symbol=sym, asset_class=asset_class)
        else:
            ref = InstrumentRef(
                symbol=item.symbol.strip().upper(),
                asset_class=item.asset_class,
                metadata=dict(item.metadata),
            )
        if not ref.symbol:
            return
        # duplicates: keep first, mark known
        if ref.symbol not in self._items:
            self._items[ref.symbol] = ref
            self._status[ref.symbol] = InstrumentStatus.AVAILABLE

    def enumerate(self) -> list[InstrumentRef]:
        return [self._items[k] for k in sorted(self._items.keys())]

    def symbols(self) -> list[str]:
        return sorted(self._items.keys())

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def set_status(self, symbol: str, status: InstrumentStatus) -> None:
        sym = symbol.upper()
        if sym in self._status:
            self._status[sym] = status

    def status(self, symbol: str) -> InstrumentStatus:
        return self._status.get(symbol.upper(), InstrumentStatus.UNKNOWN)

    def get(self, symbol: str) -> Optional[InstrumentRef]:
        return self._items.get(symbol.upper())
