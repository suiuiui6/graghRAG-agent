"""Deterministic offline demo endpoint."""

import json
from pathlib import Path

from fastapi import APIRouter


router = APIRouter()
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "offline" / "sample.json"


@router.get("/demo/sample")
async def get_demo_sample() -> dict:
    """Return the checked-in, provider-free sample answer and its grounding."""
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)
