"""Command-line entry point for the legacy SQLite migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402  # CLI launched as a file

from persistence.migration.errors import (
    BackupError,
    MigrationError,
    LegacyFormatError,
    SourceChangedError,
    TargetConflictError,
)
from persistence.migration.service import LegacyMigrationService


_EXIT_CODES = {
    "success": 0,
    "noop": 0,
    "source_changed": 2,
    "format": 3,
    "target_conflict": 4,
    "backup": 5,
    "internal": 6,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy JSON state into SQLite")
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--source-key", default="legacy")
    parser.add_argument("--import-version", required=True)
    args = parser.parse_args()
    try:
        result = LegacyMigrationService(db_path=args.db, source_root=args.source_root, backup_root=args.backup_root).migrate(
            source_key=args.source_key, import_version=args.import_version
        )
    except SourceChangedError as error:
        sys.stdout.write(json.dumps({"status": "source_changed", "error": str(error)}, ensure_ascii=False) + "\n")
        return _EXIT_CODES["source_changed"]
    except LegacyFormatError as error:
        sys.stdout.write(json.dumps({"status": "format_error", "error": str(error)}, ensure_ascii=False) + "\n")
        return _EXIT_CODES["format"]
    except TargetConflictError as error:
        sys.stdout.write(json.dumps({"status": "target_conflict", "error": str(error)}, ensure_ascii=False) + "\n")
        return _EXIT_CODES["target_conflict"]
    except BackupError as error:
        sys.stdout.write(json.dumps({"status": "backup_error", "error": str(error)}, ensure_ascii=False) + "\n")
        return _EXIT_CODES["backup"]
    except (MigrationError, ValueError, OSError) as error:
        sys.stdout.write(json.dumps({"status": "migration_error", "error": str(error)}, ensure_ascii=False) + "\n")
        return _EXIT_CODES["internal"]
    except Exception:
        sys.stdout.write(json.dumps({"status": "migration_error", "error": "migration failed"}, ensure_ascii=False) + "\n")  # noqa: BLE001  # CLI boundary must not expose internals
        return _EXIT_CODES["internal"]
    sys.stdout.write(json.dumps({"status": result.status, "counts": result.counts}, ensure_ascii=False) + "\n")
    return _EXIT_CODES["noop" if result.status == "noop" else "success"]


if __name__ == "__main__":
    sys.exit(main())
