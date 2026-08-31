"""Core primitives for CRYPTO.

Phase 1 adds typed configuration and a secure CredentialStore abstraction.
No exchange, ML, or execution logic lives here yet.
"""

from crypto.core.config import (
    SCHEMA_VERSION,
    AppConfig,
    ConfigError,
    ExchangeConfig,
    HardwareConfig,
    MLConfig,
    RiskConfig,
    RuntimeConfig,
)
from crypto.core.credentials import (
    CredentialBackendError,
    CredentialError,
    CredentialNotFoundError,
    CredentialStore,
    CredentialValidationError,
    ExchangeCredentials,
    InMemoryCredentialStore,
    create_credential_store,
)
from crypto.core.types import (
    AccountId,
    ExchangeId,
    HardwareProfile,
    SecretStr,
    Severity,
)

__all__ = [
    # Types
    "HardwareProfile",
    "Severity",
    "SecretStr",
    "ExchangeId",
    "AccountId",
    # Config
    "SCHEMA_VERSION",
    "AppConfig",
    "RuntimeConfig",
    "ExchangeConfig",
    "RiskConfig",
    "HardwareConfig",
    "MLConfig",
    "ConfigError",
    # Credentials
    "CredentialStore",
    "InMemoryCredentialStore",
    "ExchangeCredentials",
    "create_credential_store",
    "CredentialError",
    "CredentialValidationError",
    "CredentialNotFoundError",
    "CredentialBackendError",
]
