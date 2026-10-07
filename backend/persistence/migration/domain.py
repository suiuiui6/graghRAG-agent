"""Migration domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceFile:
    source_path: str
    relative_path: str
    content: bytes
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ParsedLegacy:
    tasks: tuple[dict[str, Any], ...]
    documents: tuple[dict[str, Any], ...]
    kg_versions: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class MigrationResult:
    status: str
    counts: dict[str, int]
    source_sha256: str
    backup_relpath: str | None = None
    committed_at: datetime | None = None
