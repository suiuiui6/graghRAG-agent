"""Deterministic offline demo endpoint."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException


router = APIRouter()
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "offline" / "sample.json"


@router.get("/demo/sample")
async def get_demo_sample() -> dict:
    """Return the checked-in, provider-free sample answer and its grounding."""
    try:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            payload = json.load(fixture_file)
        if not isinstance(payload, dict):
            raise ValueError("offline demo fixture must contain an object")
        return payload
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Offline demo fixture is unavailable.",
        ) from exc
