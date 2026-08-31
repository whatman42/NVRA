# Autonomous Trading

After **administrative setup** (register, license/device, broker credentials), NVRA runs trading **without** per-reboot GUI, login, or manual ARM.

| Concern | Mode |
|---------|------|
| Administration | **Manual** (once) |
| DEMO | **Autonomous** |
| PAPER | **Autonomous** |
| LIVE | **Autonomous** after admin sets `autonomous_live` |
| Restart | **Automatic** headless |
| GUI | **Optional** observer |
| Recovery | **Automatic** (bounded retries → SAFE_MODE) |
| Manual ARM each reboot | **Not required** when policy is set |

## Safety (unchanged algorithms)

```
ML → Decision → Governor → Risk → Independent Safety Gate → Execution → Broker
```

ML and Governor **cannot** bypass the independent capital/authorization gates.

LIVE still requires runtime prechecks: license, device, credentials available, broker, reconciliation, risk/governor, config, artifact integrity. Any failure → **SAFE_MODE**, no orders.

## Administrative policy (no secrets)

File: `~/.nvrafx/autonomous_trading_policy.json` (0600)

```json
{
  "schema_version": 1,
  "trading_mode": "LIVE",
  "autonomous_live": true,
  "autonomous_enabled": true,
  "updated_at": 0,
  "source": "administrative"
}
```

Never stores password, API key, token, or session.

Enable (from admin tooling / Python):

```python
from god.live.autonomous_policy import enable_autonomous_live, enable_autonomous_paper
enable_autonomous_paper(path)   # DEMO/PAPER autonomous
enable_autonomous_live(path)    # LIVE autonomous authorization
```

## Headless auto-start

```text
NVRAFX.exe --autostart --headless
```

- No `window.show()`
- No login prompt
- Loads policy → safety chain → RUNNING or SAFE_MODE

Task Scheduler / HKCU Run must use `--autostart --headless`.

## Restart flow

```text
PC restart → auto-start headless → load policy → LICENSE… → RISK →
  if LIVE+autonomous_live and prechecks PASS → RUNNING LIVE
  else if PAPER/DEMO → RUNNING paper path
  else → SAFE_MODE (no orders)
```
