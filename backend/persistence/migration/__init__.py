"""Legacy JSON/KG to SQLite migration package."""

from .domain import MigrationResult
from .errors import (
    BackupError,
    LegacyFormatError,
    MigrationError,
    SourceChangedError,
    TargetConflictError,
)
from .service import LegacyMigrationService

__all__ = [
    "BackupError",
    "LegacyFormatError",
    "LegacyMigrationService",
    "MigrationError",
    "MigrationResult",
    "SourceChangedError",
    "TargetConflictError",
]
