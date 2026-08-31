# GUI

Optional **PySide6**. Backend publishes `GuiSnapshot` to `SnapshotBus` (≥500 ms). GUI polls only — no tick subscription, no network/ML/recovery on Qt thread.

First-run wizard collects exchange + Telegram credentials into **CredentialStore** only; secrets cleared from wizard memory after store.

ULTRA_LITE: increase refresh interval; no animations/charts required.
