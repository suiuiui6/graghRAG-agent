"""Health check endpoint — §3.2.4"""

import json, os, time
from fastapi import APIRouter
from models import HealthResponse
from dotenv import load_dotenv

# Load environment variables
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)

router = APIRouter()
_START_TIME = time.time()

BASE = os.path.dirname(os.path.dirname(__file__))
KG_DIR = os.path.join(BASE, "output", "kg")


def _count_kg_nodes() -> int:
    """Count total nodes across all KGs (subdirectories + default)."""
    total = 0
    if os.path.isdir(KG_DIR):
        for entry in os.listdir(KG_DIR):
            entry_path = os.path.join(KG_DIR, entry)
            n_path = os.path.join(entry_path, "nodes.json")
            if os.path.isdir(entry_path) and os.path.exists(n_path):
                try:
                    with open(n_path, encoding="utf-8") as f:
                        total += len(json.load(f).get("nodes", []))
                except Exception:
                    pass
        # Also check default
        default_n = os.path.join(KG_DIR, "nodes.json")
        if os.path.exists(default_n):
            try:
                with open(default_n, encoding="utf-8") as f:
                    total += len(json.load(f).get("nodes", []))
            except Exception:
                pass
    return total


@router.get("/health", response_model=HealthResponse)
async def health_check():
    # Dynamic document count from store
    try:
        from routes import get_docs_snapshot
        doc_count = len(get_docs_snapshot())
    except Exception:
        doc_count = 0

    # Dynamic KG node count
    kg_nodes = _count_kg_nodes()

    # Query count from shared counter
    try:
        from routes import get_query_count
        qc = get_query_count()
    except Exception:
        qc = 0

    # Check environment variables for API availability
    mineru_token = os.getenv("MINERU_API_TOKEN", "").strip()
    langextract_key = os.getenv("LANGEXTRACT_API_KEY", "").strip()

    # Debug: print to console
    print(f"[health] MINERU_API_TOKEN length: {len(mineru_token)}")
    print(f"[health] LANGEXTRACT_API_KEY length: {len(langextract_key)}")

    # MinerU: check if token exists and is not empty
    mineru_status = "ok" if mineru_token and len(mineru_token) > 10 else "unconfigured"

    # DeepSeek/LangExtract: check if API key exists and is not empty
    deepseek_status = "ok" if langextract_key and len(langextract_key) > 10 else "unconfigured"

    print(f"[health] MinerU status: {mineru_status}")
    print(f"[health] DeepSeek status: {deepseek_status}")

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=int(time.time() - _START_TIME),
        components={
            "api_server": "ok",
            "mineru_api": mineru_status,
            "deepseek_api": deepseek_status,
            "kg_store": "ok",
        },
        stats={
            "total_documents": doc_count,
            "total_kg_nodes": kg_nodes,
            "total_queries_served": qc,
        },
    )
