"""Security middleware — rate limiting, file access tokens, ngrok defense."""

import hashlib, os, time, uuid
from fastapi import HTTPException, Request

# Generate a random file access token at startup
FILE_ACCESS_TOKEN = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]

# Simple in-memory rate limiter
_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 60       # max requests
RATE_WINDOW = 60.0    # per window (seconds)


def get_file_access_token() -> str:
    """Return the current file access token."""
    return FILE_ACCESS_TOKEN


def token_log_hint(token: str) -> str:
    """Describe token availability without disclosing credential material."""
    return "[configured]" if token else "[unconfigured]"


def verify_file_token(request: Request):
    """Verify the ?token= parameter for file access. Skips check for localhost/127.0.0.1."""
    host = request.client.host if request.client else "unknown"
    if host in ("127.0.0.1", "localhost", "::1"):
        return  # Local requests bypass token check
    token = request.query_params.get("token", "")
    if token != FILE_ACCESS_TOKEN:
        raise HTTPException(403, detail="Missing or invalid file access token")


def check_rate_limit(request: Request) -> bool:
    """Simple sliding-window rate limiter. Returns True if allowed."""
    host = request.client.host if request.client else "unknown"
    if host in ("127.0.0.1", "localhost", "::1"):
        return True  # Local requests are not rate-limited

    now = time.time()
    window_start = now - RATE_WINDOW
    if host not in _rate_store:
        _rate_store[host] = []
    _rate_store[host] = [t for t in _rate_store[host] if t > window_start]
    if not _rate_store[host]:
        del _rate_store[host]
        _rate_store[host] = []
    if len(_rate_store[host]) >= RATE_LIMIT:
        return False
    _rate_store[host].append(now)
    return True
