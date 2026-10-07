"""SQLite transaction helper for migration commit-boundary validation."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Callable, Iterator

from persistence.sqlite import _configure_connection


@contextmanager
def transaction_with_pre_commit(
    db_path: str | Path,
    *,
    pre_commit: Callable[[], None],
) -> Iterator[sqlite3.Connection]:
    """Run a migration transaction and validate immediately before committing.

    This deliberately does not compose the generic ``transaction`` context
    manager.  Its ``yield`` resumes only after the caller's body returns, which
    would leave an injection window before the generic manager commits.  The
    callback and commit are kept in this helper's single exit path instead.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    try:
        _configure_connection(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            pre_commit()
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
    finally:
        connection.close()
