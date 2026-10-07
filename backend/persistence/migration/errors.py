"""Stable exceptions for legacy migration callers and CLI."""


class MigrationError(Exception):
    """Base class for safe, user-facing migration failures."""


class LegacyFormatError(MigrationError):
    """Legacy input is malformed, incomplete, or unsafe to infer."""


class BackupError(MigrationError):
    """A byte-preserving source backup could not be completed."""


class SourceChangedError(MigrationError):
    """The same source/version was already imported with different bytes."""


class TargetConflictError(MigrationError):
    """The target contains records that a migration must not replace."""
