#!/usr/bin/env python3
"""GraphRAG Backend Server — FastAPI v1.0"""

import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=True)  # Force override system environment variables

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routes.health import router as health_router
from routes.ingest import router as ingest_router
from routes.query import router as query_router
from routes.documents import router as documents_router
from routes.graph import router as graph_router
from security import FILE_ACCESS_TOKEN, check_rate_limit, token_log_hint


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload KG + show security info
    try:
        from routes.query import _load_kg
        _load_kg()
        print("[startup] KG loaded successfully")
    except Exception as e:
        print(f"[startup] KG load warning: {e}")
    print(f"[security] File access token: {token_log_hint(FILE_ACCESS_TOKEN)}")
    print("[security] File access requires the runtime token query parameter.")
    yield


app = FastAPI(
    title="GraphRAG Backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # Increase upload size limit
    max_upload_size=200 * 1024 * 1024,  # 200 MB — supports large PDFs
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limit middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not check_rate_limit(request):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
    return await call_next(request)

# Mount routes
app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(ingest_router, prefix="/api/v1", tags=["Ingest"])
app.include_router(query_router, prefix="/api/v1", tags=["Query"])
app.include_router(documents_router, prefix="/api/v1", tags=["Documents"])
app.include_router(graph_router, prefix="/api/v1", tags=["Graph"])


@app.get("/")
async def root():
    return {"service": "GraphRAG Backend API", "version": "1.0.0", "docs": "/docs"}
