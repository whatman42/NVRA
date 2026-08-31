# NVRA V7 Runbook

## Recovery
1. Process/PC restart enters RECOVERY.
2. Load durable order journal.
3. Reconnect providers/broker.
4. Fetch balance, positions, open orders and fills.
5. Reconcile local vs external state.
6. Any unexplained mismatch or UNKNOWN order enters SAFE_MODE.
7. Never retry an order solely because a previous request timed out.

## IDX validation
Order checks cover lot size, configurable tick rules, session constraints and configurable ARA/ARB. Rules are versioned/config-driven so regulatory changes do not require source changes.

## Costs
Commission, exchange charges, tax and execution costs are configuration-driven. Do not treat example rates as legal/tax advice.
