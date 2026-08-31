# Control Plane

GUI and Telegram **never** call exchange/order APIs directly.

```
UI (GUI / Telegram)
        ↓
ControlPlane (auth + audit)
        ↓
RiskEngine / ExecutionEngine / Recovery / CredentialStore
```

Critical commands require PIN session. Emergency stop sets runtime safety flags without mutating `RiskPolicy`.
