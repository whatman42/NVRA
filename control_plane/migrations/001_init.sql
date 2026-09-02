CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL, status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS licenses (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  username TEXT NOT NULL, status TEXT NOT NULL, issued_at TEXT NOT NULL,
  expires_at TEXT, signature TEXT NOT NULL, payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  status TEXT NOT NULL, client_version TEXT, os_name TEXT, hostname TEXT, last_seen TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, device_id TEXT NOT NULL,
  token_hash TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS heartbeats (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, device_id TEXT NOT NULL, license_id TEXT NOT NULL,
  client_version TEXT, ts TIMESTAMPTZ NOT NULL DEFAULT now(), status TEXT, state_hash TEXT,
  runtime_status TEXT, safe_mode BOOLEAN DEFAULT false
);
CREATE TABLE IF NOT EXISTS policies (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, version INT NOT NULL, payload_json JSONB NOT NULL,
  signature TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT, result TEXT,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(), request_id TEXT, details_json JSONB
);
