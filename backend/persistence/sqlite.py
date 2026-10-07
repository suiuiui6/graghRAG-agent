"""SQLite connection and transaction helpers for persistence storage."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Iterator
import time


_BUSY_TIMEOUT_MS = 10_000
_WAL_MAX_ATTEMPTS = 5
_WAL_RETRY_DELAYS_SECONDS = (0.01, 0.05, 0.1, 0.2)


def _is_database_locked(error: sqlite3.OperationalError) -> bool:
    return "database is locked" in str(error).lower()


def _enable_wal_with_retry(connection: sqlite3.Connection) -> None:
    for attempt in range(_WAL_MAX_ATTEMPTS):
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as error:
            if not _is_database_locked(error) or attempt == _WAL_MAX_ATTEMPTS - 1:
                raise
            time.sleep(_WAL_RETRY_DELAYS_SECONDS[attempt])


def _configure_connection(connection: sqlite3.Connection) -> None:
    """Apply connection-local safety pragmas before yielding a connection."""
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    _enable_wal_with_retry(connection)


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a short-lived configured SQLite connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    try:
        _configure_connection(connection)
        yield connection
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def transaction(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Run one atomic BEGIN IMMEDIATE transaction."""
    with connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
