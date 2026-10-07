"""Strict parsing helpers for persisted migration timestamps."""

from __future__ import annotations

from datetime import datetime


def parse_timezone_aware_datetime(value: object, *, field_name: str) -> datetime:
    """Parse an ISO datetime and reject invalid or timezone-naive values."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid ISO datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed
