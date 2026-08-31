"""Runtime host: paths, entrypoint, migrations, freeze safety."""

from crypto.runtime.entrypoint import main, run_application
from crypto.runtime.migrate import (
    CURRENT_SCHEMA_VERSION,
    MigrationResult,
    open_and_migrate,
)
from crypto.runtime.migrate import (
    migrate as migrate_schema,
)
from crypto.runtime.paths import (
    DeployMode,
    PathResolver,
    application_root,
    detect_deploy_mode,
    get_resolver,
    is_frozen,
    set_resolver,
    user_data_root,
    write_portable_marker,
)

__all__ = [
    "main",
    "run_application",
    "PathResolver",
    "DeployMode",
    "application_root",
    "detect_deploy_mode",
    "user_data_root",
    "write_portable_marker",
    "get_resolver",
    "set_resolver",
    "is_frozen",
    "CURRENT_SCHEMA_VERSION",
    "MigrationResult",
    "migrate_schema",
    "open_and_migrate",
]
