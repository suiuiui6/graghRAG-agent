"""Byte-preserving legacy source backup and verification."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

from .datetime_utils import parse_timezone_aware_datetime
from .domain import SourceFile
from .errors import BackupError


def _safe_relative_path(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise BackupError(f"backup manifest {field_name} is unsafe")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise BackupError(f"backup manifest {field_name} is unsafe")
    return path.as_posix()


def _aggregate_sha256(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["relative_path"]):
        digest.update(entry["relative_path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["content"])
        digest.update(b"\0")
    return digest.hexdigest()


def _source_aggregate_sha256(sources: tuple[SourceFile, ...]) -> str:
    digest = hashlib.sha256()
    for source in sorted(sources, key=lambda item: item.relative_path):
        digest.update(source.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.content)
        digest.update(b"\0")
    return digest.hexdigest()


def _new_batch_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    suffix = 0
    while True:
        batch_dir = root / ("b" if suffix == 0 else f"b{suffix}")
        try:
            batch_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            suffix += 1
            continue
        return batch_dir


def _safe_attempt_id(source_key: str, import_version: str) -> str:
    payload = json.dumps(
        [source_key, import_version], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fallback_failure_directory(root: Path) -> Path:
    """Choose a directory without using caller-controlled values in its path."""
    if root.exists() and root.is_dir():
        return root
    return root.parent / "migration-failures"


_SENSITIVE_ERROR_VALUE_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|"
    r"bearer|password|passwd|secret|token)\b\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
_BEARER_VALUE_RE = re.compile(r"(?i)(\bbearer\s+)[^\s,;}]+")
_KNOWN_SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){2})\b")


def _safe_error_message(error: BaseException) -> str:
    """Keep error text useful without persisting common credential-shaped values."""
    message = str(error)
    message = _BEARER_VALUE_RE.sub(r"\1[REDACTED]", message)
    message = _SENSITIVE_ERROR_VALUE_RE.sub(r"\1[REDACTED]", message)
    return _KNOWN_SECRET_RE.sub("[REDACTED]", message)


def _cause_chain(error: BaseException) -> list[dict[str, str]]:
    """Serialize linked exceptions without tracebacks, reprs, or arbitrary fields."""
    chain: list[dict[str, str]] = []
    pending = [cause for cause in (error.__cause__, error.__context__) if cause is not None]
    seen: set[int] = set()
    while pending and len(chain) < 32:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(
            {
                "error_type": type(current).__name__,
                "error_message": _safe_error_message(current),
            }
        )
        for linked in (current.__cause__, current.__context__):
            if linked is not None and id(linked) not in seen:
                pending.append(linked)
    return chain


def _failure_payload(
    error: Exception, *, source_key: str | None = None, import_version: str | None = None
) -> dict[str, Any]:
    message = _safe_error_message(error)
    payload: dict[str, Any] = {
        # Keep ``error`` for consumers of the original evidence format.
        "error": message,
        "error_type": type(error).__name__,
        "error_message": message,
        "cause_chain": _cause_chain(error),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if source_key is not None:
        payload["source_key"] = source_key
    if import_version is not None:
        payload["import_version"] = import_version
    return payload


def write_fallback_failure_evidence(
    backup_root: str | Path,
    error: Exception,
    *,
    source_key: str,
    import_version: str,
) -> None:
    """Record a failure before a batch directory exists, using only safe paths."""
    root = Path(backup_root).resolve()
    directory = _fallback_failure_directory(root)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.is_dir():
            raise OSError("migration failure evidence directory is not a directory")
        path = directory / f"{_safe_attempt_id(source_key, import_version)}.failure.json"
        payload = json.dumps(
            _failure_payload(error, source_key=source_key, import_version=import_version),
            ensure_ascii=False,
            indent=2,
        )
        path.write_text(payload, encoding="utf-8")
    except (OSError, TypeError) as evidence_error:
        raise BackupError(
            f"migration failure evidence could not be written: {evidence_error}"
        ) from evidence_error


def create_backup(
    sources: tuple[SourceFile, ...],
    backup_root: str | Path,
    *,
    source_key: str,
    import_version: str,
    source_sha256: str | None = None,
) -> tuple[tuple[SourceFile, ...], str]:
    """Copy and verify every source, preserving partial failure evidence."""
    root = Path(backup_root).resolve()
    batch_dir: Path | None = None
    entries: list[dict[str, object]] = []
    backed_up: list[SourceFile] = []
    try:
        batch_dir = _new_batch_dir(root)
        for index, source in enumerate(sources):
            safe_name = f"{index:04d}-{Path(source.relative_path).name}"
            destination = batch_dir / safe_name
            shutil.copyfile(source.source_path, destination)
            copied = destination.read_bytes()
            copied_hash = hashlib.sha256(copied).hexdigest()
            if len(copied) != source.size or copied_hash != source.sha256:
                raise BackupError(f"backup verification failed: {source.relative_path}")
            after = Path(source.source_path).read_bytes()
            if len(after) != source.size or hashlib.sha256(after).hexdigest() != source.sha256:
                raise BackupError(f"source changed during backup: {source.relative_path}")
            entries.append(
                {
                    "source_path": source.source_path,
                    "relative_path": source.relative_path,
                    "backup_relpath": safe_name,
                    "size": source.size,
                    "sha256": source.sha256,
                    "content": source.content,
                }
            )
            backed_up.append(
                SourceFile(
                    source_path=str(destination),
                    relative_path=source.relative_path,
                    content=copied,
                    size=len(copied),
                    sha256=copied_hash,
                )
            )

        aggregate = source_sha256 or _source_aggregate_sha256(sources)
        manifest = {
            "source_key": source_key,
            "import_version": import_version,
            "source_sha256": aggregate,
            "migration_batch": batch_dir.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": [
                {key: value for key, value in entry.items() if key != "content"}
                for entry in entries
            ],
        }
        temporary = batch_dir / "manifest.json.tmp"
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(batch_dir / "manifest.json")
    except (OSError, BackupError) as error:
        if batch_dir is None:
            try:
                write_fallback_failure_evidence(
                    root,
                    error,
                    source_key=source_key,
                    import_version=import_version,
                )
            except Exception as evidence_error:  # noqa: BLE001  # preserve the backup failure as the cause
                raise BackupError(
                    "legacy source backup failed and fallback failure evidence could not be written: "
                    f"{evidence_error}"
                ) from error
            raise BackupError("legacy source backup directory could not be created") from error
        evidence = batch_dir / "failure.json"
        try:
            evidence.write_text(
                json.dumps(
                    {
                        **_failure_payload(
                            error, source_key=source_key, import_version=import_version
                        ),
                        "files": [
                            {key: value for key, value in entry.items() if key != "content"}
                            for entry in entries
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as evidence_error:
            raise BackupError(
                f"backup failed and failure evidence could not be written: {evidence_error}"
            ) from error
        raise error if isinstance(error, BackupError) else BackupError("legacy source backup failed") from error
    return tuple(backed_up), batch_dir.relative_to(root).as_posix()


def verify_backup(
    backup_root: str | Path,
    backup_relpath: str,
    *,
    source_key: str,
    import_version: str,
    source_sha256: str,
) -> None:
    """Verify a ledger backup can be reconstructed and its manifest is intact."""
    root = Path(backup_root).resolve()
    relative = _safe_relative_path(backup_relpath, field_name="backup_relpath")
    batch_dir = (root / relative).resolve()
    if not batch_dir.is_relative_to(root) or not batch_dir.is_dir():
        raise BackupError("recorded legacy backup directory is unavailable")
    manifest_path = batch_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupError("recorded legacy backup manifest is unreadable") from error
    if not isinstance(manifest, dict):
        raise BackupError("recorded legacy backup manifest is invalid")
    try:
        parse_timezone_aware_datetime(manifest["created_at"], field_name="manifest.created_at")
    except (KeyError, ValueError) as error:
        raise BackupError("recorded legacy backup manifest has an invalid created_at") from error
    if (
        manifest.get("source_key") != source_key
        or manifest.get("import_version") != import_version
        or manifest.get("source_sha256") != source_sha256
        or manifest.get("migration_batch") != batch_dir.name
    ):
        raise BackupError("recorded legacy backup manifest does not match the ledger")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BackupError("recorded legacy backup manifest has no files")

    entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_source_paths: set[str] = set()
    seen_backup_paths: set[str] = set()
    expected_fields = {"source_path", "relative_path", "backup_relpath", "size", "sha256"}
    for item in files:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise BackupError("recorded legacy backup manifest contains an invalid file")
        source_path = item["source_path"]
        if not isinstance(source_path, str) or not source_path:
            raise BackupError("recorded legacy backup manifest has an invalid source_path")
        source = Path(source_path)
        if not source.is_absolute() or ".." in source.parts:
            raise BackupError("recorded legacy backup manifest has an unsafe source_path")
        try:
            normalized_source = os.path.normcase(str(source.resolve()))
        except OSError as error:
            raise BackupError("recorded legacy backup manifest has an invalid source_path") from error
        if ".." in Path(normalized_source).parts:
            raise BackupError("recorded legacy backup manifest has an unsafe source_path")
        relative_source = _safe_relative_path(item["relative_path"], field_name="relative_path")
        relative_backup = _safe_relative_path(item["backup_relpath"], field_name="backup_relpath")
        if normalized_source in seen_source_paths:
            raise BackupError("recorded legacy backup manifest contains duplicate source paths")
        if os.path.normcase(Path(source).name) != os.path.normcase(Path(relative_source).name):
            raise BackupError("recorded legacy backup manifest source_path basename does not match relative_path")
        if relative_source in seen_paths:
            raise BackupError("recorded legacy backup manifest contains duplicate files")
        if relative_backup in seen_backup_paths:
            raise BackupError("recorded legacy backup manifest contains duplicate backup paths")
        if relative_backup in {"manifest.json", "manifest.json.tmp", "failure.json"}:
            raise BackupError("recorded legacy backup manifest uses a reserved backup path")
        seen_source_paths.add(normalized_source)
        seen_paths.add(relative_source)
        seen_backup_paths.add(relative_backup)
        size = item["size"]
        digest = item["sha256"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise BackupError("recorded legacy backup manifest has an invalid size")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise BackupError("recorded legacy backup manifest has an invalid hash")
        backed_up = (batch_dir / relative_backup).resolve()
        if not backed_up.is_relative_to(batch_dir) or not backed_up.is_file() or backed_up.is_symlink():
            raise BackupError("recorded legacy backup file is unavailable")
        try:
            content = backed_up.read_bytes()
        except OSError as error:
            raise BackupError("recorded legacy backup file is unreadable") from error
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise BackupError("recorded legacy backup file checksum mismatch")
        entries.append({"relative_path": relative_source, "sha256": digest, "content": content})
    if _aggregate_sha256(entries) != source_sha256:
        raise BackupError("recorded legacy backup aggregate checksum mismatch")


def write_failure_evidence(
    backup_root: str | Path,
    backup_relpath: str,
    error: Exception,
    *,
    source_key: str,
    import_version: str,
) -> None:
    """Record a post-copy validation failure without deleting the backup."""
    root = Path(backup_root).resolve()
    relative = _safe_relative_path(backup_relpath, field_name="backup_relpath")
    batch_dir = (root / relative).resolve()
    if not batch_dir.is_relative_to(root) or not batch_dir.is_dir():
        raise BackupError("cannot write migration failure evidence")
    try:
        (batch_dir / "failure.json").write_text(
            json.dumps(
                _failure_payload(
                    error,
                    source_key=source_key,
                    import_version=import_version,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as evidence_error:
        raise BackupError("migration failed and failure evidence could not be written") from evidence_error
