# NVRA Unified

This distribution preserves both original engines:
- `god/` = NVRAFX/N.U.N.G. Forex, MT5, research, decision, resilience, adaptive ML, paper portfolio.
- `src/crypto/` = CRYPTO multi-exchange, risk, execution, market, ensemble, secure credentials, Telegram modules.
- `nvra_unified/` = one supervisor, one adaptive hardware profile, one GUI/control plane, persistent configuration.

## Resource strategy
Hardware profiles are selected automatically from RAM/CPU. Low-end machines use lighter refresh/ML budgets; higher-end systems can install `requirements-ml-full.txt`. Safety/risk limits are never changed by hardware profile.

## Portfolio separation
- Each crypto broker/account is a separate logical portfolio.
- Forex reads the external MT5 account.
- IDX is signal-only with an IDR 10,000,000 simulation balance and reset function.

## Runtime lifecycle
Closing the GUI hides it to the Windows tray. The non-daemon supervisor continues until Graceful Stop completes. Force Stop exists only as an emergency operator action.

## Security
- Default requested login is implemented as username `nung` plus a PBKDF2 verifier for the supplied password; plaintext password is not stored.
- Exchange and Telegram secrets use keyring/Windows Credential Manager where available.
- Registration is controlled by `NVRA_REGISTRATION_SECRET`.
- Withdrawal is fail-closed because the supplied CRYPTO adapters explicitly disable withdrawal; no fake success is reported.
