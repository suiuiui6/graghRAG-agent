"""Health check endpoint — §3.2.4 + §6.7 Phase 3 enhancement"""

import json
import os
import time
from fastapi import APIRouter
from models import HealthResponse
from dotenv import load_dotenv

from logging_config import get_logger

logger = get_logger(__name__)

_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)

router = APIRouter()
_START_TIME = time.time()

BASE = os.path.dirname(os.path.dirname(__file__))
KG_DIR = os.path.join(BASE, "output", "kg")


def _count_kg_nodes() -> int:
    total = 0
    has_subdirs = False
    if os.path.isdir(KG_DIR):
        for entry in os.listdir(KG_DIR):
            entry_path = os.path.join(KG_DIR, entry)
            n_path = os.path.join(entry_path, "nodes.json")
            if os.path.isdir(entry_path) and os.path.exists(n_path):
                has_subdirs = True
                try:
                    with open(n_path, encoding="utf-8") as f:
                        total += len(json.load(f).get("nodes", []))
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
        if not has_subdirs:
            default_n = os.path.join(KG_DIR, "nodes.json")
            if os.path.exists(default_n):
                try:
                    with open(default_n, encoding="utf-8") as f:
                        total += len(json.load(f).get("nodes", []))
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
    return total


def _count_kg_edges() -> int:
    total = 0
    if os.path.isdir(KG_DIR):
        for entry in os.listdir(KG_DIR):
            entry_path = os.path.join(KG_DIR, entry)
            e_path = os.path.join(entry_path, "edges.json")
            if os.path.isdir(entry_path) and os.path.exists(e_path):
                try:
                    with open(e_path, encoding="utf-8") as f:
                        total += len(json.load(f).get("edges", []))
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
        if total == 0:
            default_e = os.path.join(KG_DIR, "edges.json")
            if os.path.exists(default_e):
                try:
                    with open(default_e, encoding="utf-8") as f:
                        total += len(json.load(f).get("edges", []))
                except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
                    pass
    return total


@router.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        from routes import get_docs_snapshot
        doc_count = len(get_docs_snapshot())
    except Exception:  # noqa: BLE001  # 健康检查各字段独立探测，单项失败降级为占位值，不使整体探活失败
        doc_count = 0

    kg_nodes = _count_kg_nodes()
    kg_edges = _count_kg_edges()

    try:
        from routes import get_query_count
        qc = get_query_count()
    except Exception:  # noqa: BLE001  # 健康检查各字段独立探测，单项失败降级为占位值，不使整体探活失败
        qc = 0

    try:
        from index_registry import get_runtime_recovery_status

        runtime_recovery = get_runtime_recovery_status()
    except Exception:  # noqa: BLE001  # 健康检查各字段独立探测，单项失败降级为占位值，不使整体探活失败
        runtime_recovery = {
            "bm25": {"artifact_exists": False, "loaded": False},
            "table": {"artifact_exists": False, "loaded": False},
        }

    mineru_token = os.getenv("MINERU_API_TOKEN", "").strip()
    langextract_key = os.getenv("LANGEXTRACT_API_KEY", "").strip()

    mineru_status = "ok" if mineru_token and len(mineru_token) > 10 else "unconfigured"
    deepseek_status = "ok" if langextract_key and len(langextract_key) > 10 else "unconfigured"

    # Phase 3: integrate HealthChecker probe results
    dependencies: dict = {}
    try:
        from services.health_checker import get_health_checker
        hc = get_health_checker()
        probe_results = hc.get_status()
        for name, result in probe_results.items():
            dependencies[name] = {
                "status": result.get("status", "unknown"),
                "latency_ms": result.get("latency_ms", 0),
            }
    except Exception:  # noqa: BLE001  # 健康检查各字段独立探测，单项失败降级为占位值，不使整体探活失败
        dependencies = {}

    # Compute overall health from probe results
    degraded_count = sum(1 for v in dependencies.values() if v["status"] == "degraded")
    down_count = sum(1 for v in dependencies.values() if v["status"] == "down")

    runtime_component = (
        "ok"
        if all(item.get("loaded") or not item.get("artifact_exists") for item in runtime_recovery.values())
        else "degraded"
    )

    if down_count > 0:
        overall = "unhealthy"
    elif degraded_count > 0 or runtime_component != "ok":
        overall = "degraded"
    else:
        overall = "healthy"

    logger.info("health_check",
                overall=overall, mineru=mineru_status, deepseek=deepseek_status,
                probes=list(dependencies.keys()))

    return HealthResponse(
        status=overall,
        version="1.0.0",
        uptime_seconds=int(time.time() - _START_TIME),
        components={
            "api_server": "ok",
            "mineru_api": mineru_status,
            "deepseek_api": deepseek_status,
            "kg_store": "ok",
            "chromadb": dependencies.get("chromadb", {}).get("status", "unknown"),
            "oauth2_provider": dependencies.get("oauth2_provider", {}).get("status", "unknown"),
            "feishu_bot": dependencies.get("feishu_bot", {}).get("status", "unknown"),
            "scheduler": "ok",
            "runtime_recovery": runtime_component,
        },
        stats={
            "total_documents": doc_count,
            "total_kg_nodes": kg_nodes,
            "total_kg_edges": kg_edges,
            "total_queries_served": qc,
            "queries_today": 0,
        },
        dependencies={
            **dependencies,
            "index_artifacts": runtime_recovery,
        },
    )


@router.get("/capabilities")
async def capabilities():
    return {
        "capabilities": ["query", "metadata", "ingest", "feedback", "graph", "export"],
    }
