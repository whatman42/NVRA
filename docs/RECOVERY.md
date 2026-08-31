# Recovery

Startup is composed as:

`LICENSE_CHECK → LOAD_STATE → BROKER_CONNECT → RECONCILIATION → RISK_GOVERNOR → READY → RUNNING`

A stage failure is fail-closed. The runtime enters `SAFE_MODE`, retries according to its configured policy (maximum five attempts where applicable), and only resumes when the failed prerequisite is healthy.

Recovery must not bypass risk/governor checks or convert a failed integrity check into a successful startup. GUI failures are isolated from the core runtime.
