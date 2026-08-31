# External references evaluated for NVRA MT adapter

NVRA does **not** vendor or auto-execute third-party trading strategies.
Patterns adopted (API shapes / reliability only):

| Repo | Useful for NVRA | Not used |
|------|-----------------|----------|
| [BonneVoyager/MetaTrader4-Bridge](https://github.com/BonneVoyager/MetaTrader4-Bridge) | Request id protocol, account/orders/rates ops, pipe schema → `ipc_protocol.py` | Node stack; open bind |
| [ejtraderLabs/Metatrader5-Docker](https://github.com/ejtraderLabs/Metatrader5-Docker) | Optional lab terminal via Docker/VNC (ops doc only) | Not required in core; Wine complexity |
| [samuraitaiga/py-metatrader](https://github.com/samuraitaiga/py-metatrader) | Historical idea of driving terminal for backtest | Python 2.7 / MT4 only — not production path |
| [geraked/metatrader5](https://github.com/geraked/metatrader5) | — | MQL5 strategy EAs — **not** imported into brain |
| [abhidp/tradingview-to-metatrader5](https://github.com/abhidp/tradingview-to-metatrader5) | — | Webhook→MT5 bypasses NVRA risk — **rejected** as direct path |
| [slowfound/metatrader5-quant-server-python](https://github.com/slowfound/metatrader5-quant-server-python) | Ops/monitoring layout ideas | Full stack not embedded |

## NVRA path (unchanged)

```
Decision → Risk → Authorization → Firewall → Idempotency → MT5 Adapter → Terminal → Reconcile
```

Default: DEMO only (`allow_live_account=False`). Bind policy: `127.0.0.1`.
