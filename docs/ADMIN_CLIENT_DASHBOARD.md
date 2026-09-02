# Admin Client Dashboard

Server-side Admin view of all CLIENT tenants. Enforcement is in `god.control_plane` — not GUI menus.

## Access

| Actor | Scope |
|-------|--------|
| SUPER_ADMIN | All clients |
| CLIENT | Own account only |

## Surfaces (data models)

| Section | Source |
|---------|--------|
| Overview | `admin_clients` / `admin_dashboard_summary` |
| Client detail | `admin_view_client` / `client_detail` |
| Devices / Sessions / License | store entities in detail payload |
| Heartbeats | last age + `heartbeat_class` (never auto-revoke on timeout) |
| Portfolio / Risk / Model / System | optional telemetry, secrets stripped |
| Audit | `store.audit` events |

## Status (from real state)

| Status | Meaning |
|--------|---------|
| ONLINE | heartbeat age < 5 min |
| OFFLINE_GRACE | 5–15 min |
| OFFLINE | > 15 min or never |
| SAFE_MODE | recent safe_mode heartbeat |
| LICENSE_BLOCKED | license/account revoked/disabled/expired |

Heartbeat timeout alone is **CLIENT_OFFLINE**, not LICENSE_REVOKED.

## Allowed admin actions

view, disable/enable client, generate/disable/revoke license, disable/revoke device, revoke session, publish model, update approved policy.

## Forbidden

bypass Risk Governor, force live order, change immutable risk ceiling, access client secrets/private keys, download master dataset/private weights.

Remote disable effect path: stop new orders → reconciliation → SAFE_MODE → blocked (not hard-kill).

## API (handlers)

- `GET` admin clients / summary / client detail → SUPER_ADMIN only  
- Client `me` / `status` / `portfolio` → scoped to actor; forged `client_id` ignored for CLIENT  

## PAPER-only

Dashboard has **no** order submission authority. Portfolio is telemetry-only.
