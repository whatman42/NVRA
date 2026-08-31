# Broker Mode Release Notes

This release adds explicit DEMO/REAL execution profiles for Binance, Tokocrypto,
INDODAX and MetaTrader 5.

REAL mode is fail-closed and requires configuration plus two independent
environment confirmations. DEMO mode cannot silently fall through to a
production exchange endpoint when native sandbox support is unavailable.

The live execution capability is present but never enabled by default.
