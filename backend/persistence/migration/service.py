"""Orchestrate source snapshot, backup, validation, and one SQLite transaction."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
from typing import Iterator

from persistence.schema import initialize_database
from persistence.sqlite import transaction

from .backup import (
    create_backup,
    verify_backup,
    write_failure_evidence,
    write_fallback_failure_evidence,
)
from .datetime_utils import parse_timezone_aware_datetime
from .domain import MigrationResult
from .errors import SourceChangedError
from .sqlite_writer import write_import
from .source_reader import aggregate_sha256, enumerate_sources, parse_sources
from .transaction import transaction_with_pre_commit


_PROCESS_LOCKS: dict[Path, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Serialize migrations in this process and across OS processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _PROCESS_LOCKS_GUARD:
        process_lock = _PROCESS_LOCKS.setdefault(path, threading.Lock())
    with process_lock:
        handle = None
        try:
            handle = open(path, "a+b")
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                while True:
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError as error:
                        if error.errno is None:
                            raise
                        time.sleep(0.05)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if handle is not None:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError as error:
                        if error.errno is None:
                            raise RuntimeError("unable to release migration lock") from error
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()


class LegacyMigrationService:
    """Import legacy state without changing the legacy source tree."""

    def __init__(self, *, db_path: str | Path, source_root: str | Path, backup_root: str | Path):
        self.db_path = Path(db_path)
        self.source_root = Path(source_root)
        self.backup_root = Path(backup_root).resolve()
        self._lock_path = self.db_path.parent / ".legacy-migration.lock"

    def _source_hash(self) -> str:
        """Hash the current source tree; kept as a patchable race-window guard."""
        return aggregate_sha256(enumerate_sources(self.source_root))

    def _assert_source_unchanged(self, expected_sha256: str) -> None:
        """Reject source mutations observed at a transaction boundary."""
        if self._source_hash() != expected_sha256:
            raise SourceChangedError("source bytes changed during migration")

    def _record_failure(
        self,
        backup_relpath: str,
        error: Exception,
        *,
        source_key: str,
        import_version: str,
    ) -> None:
        try:
            write_failure_evidence(
                self.backup_root,
                backup_relpath,
                error,
                source_key=source_key,
                import_version=import_version,
            )
        except Exception:  # noqa: BLE001  # fall back when the recorded batch is unavailable
            try:
                write_fallback_failure_evidence(
                    self.backup_root,
                    error,
                    source_key=source_key,
                    import_version=import_version,
                )
            except Exception as fallback_error:  # noqa: BLE001  # preserve the original migration failure as cause
                raise fallback_error from error

    def migrate(self, *, import_version: str, source_key: str = "legacy") -> MigrationResult:
        if not isinstance(import_version, str) or not import_version.strip():
            raise ValueError("import_version must be a non-empty string")
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError("source_key must be a non-empty string")

        with _file_lock(self._lock_path):
            try:
                initialize_database(self.db_path)
            except Exception as error:  # noqa: BLE001  # persist initialization failure before re-raising
                try:
                    write_fallback_failure_evidence(
                        self.backup_root,
                        error,
                        source_key=source_key,
                        import_version=import_version,
                    )
                except Exception as evidence_error:  # noqa: BLE001  # preserve initialization failure as the cause
                    raise evidence_error from error
                raise

            try:
                sources = enumerate_sources(self.source_root)
            except Exception as error:  # noqa: BLE001  # preserve source enumeration failures with evidence
                try:
                    write_fallback_failure_evidence(
                        self.backup_root,
                        error,
                        source_key=source_key,
                        import_version=import_version,
                    )
                except Exception as evidence_error:  # noqa: BLE001  # preserve the enumeration failure as the cause
                    raise evidence_error from error
                raise
            source_sha256 = aggregate_sha256(sources)

            # This short transaction is only the ledger preflight.  It avoids
            # creating a new backup for the normal repeated-import/no-op path.
            # No backup batch exists yet, so failures must use fallback evidence.
            try:
                with transaction(self.db_path) as connection:
                    ledger = connection.execute(
                        """SELECT source_sha256, backup_relpath, counts_json, committed_at
                        FROM legacy_imports
                        WHERE source_key = ? AND import_version = ?""",
                        (source_key, import_version),
                    ).fetchone()
            except Exception as error:  # noqa: BLE001  # preserve preflight failures with evidence
                try:
                    write_fallback_failure_evidence(
                        self.backup_root,
                        error,
                        source_key=source_key,
                        import_version=import_version,
                    )
                except Exception as evidence_error:  # noqa: BLE001  # preserve the preflight failure as the cause
                    raise evidence_error from error
                raise
            if ledger is not None:
                try:
                    if ledger["source_sha256"] != source_sha256:
                        raise SourceChangedError("source bytes changed for an existing import")
                    verify_backup(
                        self.backup_root,
                        ledger["backup_relpath"],
                        source_key=source_key,
                        import_version=import_version,
                        source_sha256=source_sha256,
                    )
                    committed_at = parse_timezone_aware_datetime(
                        ledger["committed_at"], field_name="legacy_imports.committed_at"
                    )
                except Exception as error:  # noqa: BLE001  # evidence must cover ledger failures
                    self._record_failure(
                        ledger["backup_relpath"],
                        error,
                        source_key=source_key,
                        import_version=import_version,
                    )
                    raise
                return MigrationResult(
                    status="noop",
                    counts={},
                    source_sha256=source_sha256,
                    backup_relpath=ledger["backup_relpath"],
                    committed_at=committed_at,
                )

            backed_up, backup_relpath = create_backup(
                sources,
                self.backup_root,
                source_key=source_key,
                import_version=import_version,
                source_sha256=source_sha256,
            )
            try:
                parsed = parse_sources(backed_up)
                # A successful per-file copy does not protect against a later source
                # mutation. Re-snapshot before opening the business transaction.
                self._assert_source_unchanged(source_sha256)

                with transaction_with_pre_commit(
                    self.db_path,
                    pre_commit=lambda: self._assert_source_unchanged(source_sha256),
                ) as connection:
                    # The OS lock closes the race with another migration process; the
                    # second check also protects callers that manipulate the DB directly.
                    ledger = connection.execute(
                        "SELECT source_sha256, backup_relpath, committed_at FROM legacy_imports "
                        "WHERE source_key = ? AND import_version = ?",
                        (source_key, import_version),
                    ).fetchone()
                    if ledger is not None:
                        try:
                            if ledger["source_sha256"] != source_sha256:
                                raise SourceChangedError("source bytes changed for an existing import")
                            verify_backup(
                                self.backup_root,
                                ledger["backup_relpath"],
                                source_key=source_key,
                                import_version=import_version,
                                source_sha256=source_sha256,
                            )
                            committed_at = parse_timezone_aware_datetime(
                                ledger["committed_at"], field_name="legacy_imports.committed_at"
                            )
                        except Exception as error:  # noqa: BLE001  # evidence must cover ledger failures
                            self._record_failure(
                                ledger["backup_relpath"],
                                error,
                                source_key=source_key,
                                import_version=import_version,
                            )
                            raise
                        return MigrationResult(
                            status="noop",
                            counts={},
                            source_sha256=source_sha256,
                            backup_relpath=ledger["backup_relpath"],
                            committed_at=committed_at,
                        )

                    self._assert_source_unchanged(source_sha256)
                    counts = write_import(
                        connection,
                        parsed,
                        source_key=source_key,
                        import_version=import_version,
                        source_sha256=source_sha256,
                        backup_relpath=backup_relpath,
                    )
            except Exception as error:  # noqa: BLE001  # rollback first, then persist failure evidence
                self._record_failure(
                    backup_relpath,
                    error,
                    source_key=source_key,
                    import_version=import_version,
                )
                raise

        return MigrationResult(
            status="imported",
            counts=counts,
            source_sha256=source_sha256,
            backup_relpath=backup_relpath,
            committed_at=datetime.now(timezone.utc),
        )
