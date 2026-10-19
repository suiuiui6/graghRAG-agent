#!/usr/bin/env python3
"""GraphRAG Backend Server — FastAPI v1.0 + Phase 0 enterprise foundations"""

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Env ────────────────────────────────────────────────────────────────────

_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=True)

# ── Phase 0: structured logging ────────────────────────────────────────────

from logging_config import setup_logging, set_request_id, get_logger

setup_logging()
logger = get_logger(__name__)

# ── Phase 0: metrics ───────────────────────────────────────────────────────

from metrics import (
    metrics_endpoint,
    rag_requests_total,
    rag_request_duration_seconds,
    rag_documents_total,
    rag_kg_nodes_total,
    rag_kg_edges_total,
    record_cache_hit,
    record_rag_response_observability,
)

# ── Phase 0: auth ──────────────────────────────────────────────────────────

from auth import create_auth_middleware

# ── Phase 3: JWT middleware ────────────────────────────────────────────────

from middleware.jwt_middleware import create_jwt_middleware

# ── Routes ─────────────────────────────────────────────────────────────────

from routes.health import router as health_router
from routes.ingest import router as ingest_router
from routes.query import router as query_router
from routes.rag_query import router as rag_query_router
from routes.documents import router as documents_router
from routes.graph import router as graph_router
from routes.domain_dict import router as domain_dict_router
from routes.conversation import router as conversation_router
from routes.feedback import router as feedback_router
from routes.lineage import router as lineage_router
from routes.catalog import router as catalog_router
from routes.export import router as export_router
from routes.system import router as system_router
from routes.auth import router as auth_router
from routes.bot import router as bot_router
from routes.webhooks import router as webhooks_router
from routes.audit import router as audit_router
from routes.api_keys import router as api_keys_router
from routes.tenants import router as tenants_router
from routes.static import router as static_router
from security import check_rate_limit, FILE_ACCESS_TOKEN

MINERU_OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "mineru"
MIN_RUNTIME_TABLE_ROWS = 5


def _table_index_row_count(index) -> int:
    if index is None:
        return 0

    try:
        stats = index.get_stats()
        if isinstance(stats, dict):
            total_rows = stats.get("total_rows")
            if isinstance(total_rows, int):
                return total_rows
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass

    try:
        rows = index.query(top_k=MIN_RUNTIME_TABLE_ROWS + 1)
        if isinstance(rows, list):
            return len(rows)
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass

    return 0


def _iter_mineru_runtime_sources() -> list[tuple[Path, str]]:
    if MINERU_OUTPUT_DIR.is_symlink() or MINERU_OUTPUT_DIR.is_junction() or not MINERU_OUTPUT_DIR.is_dir():
        return []

    output_root = MINERU_OUTPUT_DIR.resolve()

    def safe_path(path: Path) -> bool:
        return (
            not path.is_symlink()
            and not path.is_junction()
            and path.resolve().is_relative_to(output_root)
        )

    def valid_source(path: Path) -> bool:
        if not safe_path(path) or not path.is_dir():
            return False
        markdown = path / "full.md"
        content_lists = list(path.glob("*_content_list.json"))
        return (
            safe_path(markdown)
            and markdown.is_file()
            and bool(content_lists)
            and all(safe_path(item) and item.is_file() for item in content_lists)
        )

    candidates = sorted(
        [
            path for path in MINERU_OUTPUT_DIR.iterdir()
            if not path.name.startswith(".working-") and safe_path(path) and path.is_dir()
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    sources: list[tuple[Path, str]] = []
    for mineru_dir in candidates:
        # 新任务只读取原子发布的 result；旧任务仍可读取一级有效产物。
        published_dir = mineru_dir / "result"
        if valid_source(published_dir):
            sources.append((published_dir, f"{mineru_dir.name}.pdf"))
        elif valid_source(mineru_dir):
            sources.append((mineru_dir, f"{mineru_dir.name}.pdf"))
    return sources


def _find_latest_mineru_runtime_source() -> tuple[Path, str] | None:
    sources = _iter_mineru_runtime_sources()
    return sources[0] if sources else None


def _recover_sparse_runtime_table_index() -> dict | None:
    try:
        from index_registry import get_table_index
    except Exception:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        return None

    current_rows = _table_index_row_count(get_table_index())
    if current_rows >= MIN_RUNTIME_TABLE_ROWS:
        return None

    sources = _iter_mineru_runtime_sources()
    if not sources:
        return {
            "rebuilt": False,
            "reason": "no_mineru_source",
            "table_rows_before": current_rows,
        }

    last_failure: dict | None = None
    for mineru_dir, filename in sources:
        try:
            from worker import _build_runtime_indexes_from_mineru_output

            chunks = _build_runtime_indexes_from_mineru_output(str(mineru_dir), filename)
        except Exception as exc:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            last_failure = {
                "rebuilt": False,
                "reason": f"rebuild_failed:{type(exc).__name__}",
                "table_rows_before": current_rows,
                "mineru_dir": str(mineru_dir),
                "filename": filename,
            }
            continue

        try:
            from index_registry import get_table_index as _get_table_index

            table_rows_after = _table_index_row_count(_get_table_index())
        except Exception:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            table_rows_after = 0

        if table_rows_after >= MIN_RUNTIME_TABLE_ROWS:
            return {
                "rebuilt": True,
                "reason": "ok",
                "table_rows_before": current_rows,
                "table_rows_after": table_rows_after,
                "chunks": len(chunks or []),
                "mineru_dir": str(mineru_dir),
                "filename": filename,
            }

        last_failure = {
            "rebuilt": False,
            "reason": "candidate_sparse",
            "table_rows_before": current_rows,
            "table_rows_after": table_rows_after,
            "chunks": len(chunks or []),
            "mineru_dir": str(mineru_dir),
            "filename": filename,
        }

    return last_failure


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = None
    try:
        from index_registry import restore_runtime_indexes

        recovery = restore_runtime_indexes()
        for cache_name, state in recovery.items():
            if state.get("restored"):
                record_cache_hit(f"{cache_name}_runtime_recovery")
        logger.info("runtime_indexes_recovered", recovery=recovery)
        table_recovery = _recover_sparse_runtime_table_index()
        if table_recovery is not None:
            logger.info("runtime_table_index_recovered_from_mineru", recovery=table_recovery)
    except Exception as e:  # noqa: BLE001  # 启动期索引恢复为最优努力，失败仅记录告警，不阻断服务启动
        logger.warning("runtime_index_recovery_failed", error=str(e))

    try:
        from kg_store import load_all_kg_graphs
        import routes.query as qmod

        full_g = load_all_kg_graphs()
        qmod.G_grounded = qmod._build_kg_from_full(full_g) if full_g.number_of_nodes() > 0 else None
        logger.info("kg_loaded", nodes=full_g.number_of_nodes(), edges=full_g.number_of_edges())
    except Exception as e:  # noqa: BLE001  # KG 图加载失败仅记录错误，服务仍可启动并由后续请求按需重建
        logger.error("kg_load_failed", error=str(e))

    try:
        from routes.rag_query import warm_rag_runtime

        warmed = warm_rag_runtime()
        logger.info("rag_runtime_warmed", warmed=warmed)
    except Exception as e:  # noqa: BLE001  # 运行时预热为可选优化，失败仅记录告警，不阻断服务启动
        logger.warning("rag_runtime_warmup_failed", error=str(e))

    # Update business metrics gauges
    try:
        from routes import get_docs_snapshot
        docs = get_docs_snapshot()
        rag_documents_total.set(len(docs))
        import routes.query as qmod
        if qmod.G_grounded:
            rag_kg_nodes_total.set(qmod.G_grounded.number_of_nodes())
            rag_kg_edges_total.set(qmod.G_grounded.number_of_edges())
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass

    # Phase 2: scheduled backup + cleanup
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.backup import get_backup_manager
        from services.lifecycle import get_lifecycle_manager
        from services.health_checker import get_health_checker
        scheduler = BackgroundScheduler()
        scheduler.add_job(get_backup_manager().scheduled_backup, "cron", hour=2, minute=0,
                         id="daily_backup")
        scheduler.add_job(get_lifecycle_manager().run_cleanup, "cron", hour=3, minute=0,
                         id="daily_cleanup")
        scheduler.add_job(get_health_checker().probe_all, "interval", minutes=5,
                         id="health_probe")
        scheduler.start()
        logger.info("scheduler_started", jobs=["daily_backup@02:00", "daily_cleanup@03:00",
                                                "health_probe@5min"])
    except ImportError:
        logger.warning("scheduler_skipped", reason="apscheduler not installed")
    except Exception as e:  # noqa: BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        logger.warning("scheduler_skipped", reason=str(e))

    # Phase 3: start EventBus background worker
    try:
        from services.event_bus import get_event_bus
        await get_event_bus().start()
        logger.info("event_bus_started")
    except Exception as e:  # noqa: BLE001  # EventBus 启动失败仅记录告警，事件投递降级为不可用，不阻断服务启动
        logger.warning("event_bus_start_failed", error=str(e))

    # 不得输出 token 值 —— 该 token 是 routes/documents.py:132 文件访问的 bearer 凭据。
    # 字段名刻意不含 "token"：脱敏处理器的键名规则会把任何含 token 段的键整体替换为
    # [REDACTED]，那样这个布尔值本身也会被抹掉、日志失去意义。
    logger.info("server_started", file_access_enabled=bool(FILE_ACCESS_TOKEN))
    yield
    # Shutdown
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
            pass
    try:
        from services.event_bus import get_event_bus
        await get_event_bus().stop()
    except Exception:  # noqa: S110, BLE001  # 清理为尽力而为，失败已由调用方汇总，不中断其余类别
        pass
    logger.info("server_stopped")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GraphRAG Backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    max_upload_size=200 * 1024 * 1024,
)

# Starlette executes the last registered middleware first:
# JWT -> authentication gate -> tenant resolution -> resource guard -> routes.
from services.resource_access import create_resource_guard_middleware
from middleware.tenant_middleware import create_tenant_middleware
app.middleware("http")(create_resource_guard_middleware())
app.middleware("http")(create_tenant_middleware())
app.middleware("http")(create_auth_middleware())
app.middleware("http")(create_jwt_middleware())


# Phase 0: request-id + logging middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 必须保留这次**调用**：set_request_id() 的副作用是生成并绑定 request_id
    # 到 structlog 上下文（见 logging_config.py），返回值本身此处用不到。
    # 不要写成 `rid = set_request_id()` 让 rid 悬空，更不要因"未使用"删掉调用。
    set_request_id()
    start = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        rag_request_duration_seconds.labels(endpoint=request.url.path).observe(elapsed_ms / 1000)
        rag_requests_total.labels(endpoint=request.url.path, status=str(response.status_code)).inc()
        if request.url.path.endswith("/rag/query") and hasattr(response, "body") and response.body:
            try:
                record_rag_response_observability(json.loads(response.body))
            except Exception:  # noqa: BLE001  # 可观测性埋点为旁路，响应体解析失败不应影响响应返回
                logger.debug("rag_observability_parse_failed", exc_info=True)
        return response
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        rag_requests_total.labels(endpoint=request.url.path, status="500").inc()
        raise


# Rate limit middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not check_rate_limit(request):
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
    return await call_next(request)


# Handle browser preflight before authentication; actual API requests still pass
# through the full identity and resource checks, including error responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 结构化异常边界 —— 必须在 include_router 之前注册
from errors import register_exception_handlers
register_exception_handlers(app)


# ── Routes ─────────────────────────────────────────────────────────────────

app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(ingest_router, prefix="/api/v1", tags=["Ingest"])
app.include_router(query_router, prefix="/api/v1", tags=["Query"])
app.include_router(rag_query_router, prefix="/api/v1", tags=["RAG Query"])
app.include_router(documents_router, prefix="/api/v1", tags=["Documents"])
app.include_router(graph_router, prefix="/api/v1", tags=["Graph"])
app.include_router(domain_dict_router, prefix="/api/v1", tags=["Domain Dictionary"])
app.include_router(conversation_router, prefix="/api/v1", tags=["Conversations"])
app.include_router(feedback_router, prefix="/api/v1", tags=["Feedback"])
app.include_router(lineage_router, prefix="/api/v1", tags=["Lineage"])
app.include_router(catalog_router, prefix="/api/v1", tags=["Catalog"])
app.include_router(export_router, prefix="/api/v1", tags=["Export"])
app.include_router(system_router, prefix="/api/v1", tags=["System"])
app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])
app.include_router(bot_router, prefix="/api/v1", tags=["Bot"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(audit_router, prefix="/api/v1", tags=["Audit"])
app.include_router(api_keys_router, prefix="/api/v1", tags=["API Keys"])
app.include_router(tenants_router, prefix="/api/v1", tags=["Tenants"])
app.include_router(static_router, tags=["Static"])


# Phase 0: Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    return await metrics_endpoint()


@app.get("/")
async def root():
    return {"service": "GraphRAG Backend API", "version": "1.0.0", "docs": "/docs"}
