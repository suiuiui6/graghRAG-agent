"""
RAG Query endpoint — uses the new §2.4-2.6 retrieval + prompt + generation pipeline.

Provides enhanced QA with multi-path recall (Vector + KG + BM25 + Table),
RRF reranking, and citation-verified answer generation.
"""

import os
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from config import (
    DEFAULT_ENABLE_CROSS_ENCODER,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_TOTAL_CANDIDATES,
    default_per_source_caps,
)
from models import QueryRequest, QueryResponse, SourceNode
from logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Lazy-initialized pipeline components
_rag_pipeline = None
_embedding_client = None
_vector_store = None
_init_failed = False
_init_lock = threading.Lock()


def _build_bm25_index_from_vector_store(vector_store):
    """Rebuild a minimal BM25 runtime index from persisted vector chunks."""
    if vector_store is None or not hasattr(vector_store, "_collection"):
        return None

    from doc_processor import Chunk
    from index_registry import build_bm25_from_chunks

    rows = vector_store._collection.get(include=["documents", "metadatas"])
    chunk_ids = rows.get("ids", []) or []
    documents = rows.get("documents", []) or []
    metadatas = rows.get("metadatas", []) or []
    chunks = []
    for idx, chunk_id in enumerate(chunk_ids):
        text = documents[idx] if idx < len(documents) else ""
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=text,
                content_type=metadata.get("content_type", "text"),
                metadata=None,
            )
        )
    if not chunks:
        return None
    return build_bm25_from_chunks(chunks)


def warm_rag_runtime() -> bool:
    """Warm lazy runtime components outside the first user request."""
    if not _init_rag_pipeline():
        return False

    try:
        if _embedding_client is not None:
            _embedding_client.embed_text("warmup")
    except Exception as e:  # noqa: BLE001  # 运行时预热为可选优化，失败仅记录告警，真正查询时会按需重建
        logger.warning("embedding_runtime_warmup_failed", error=str(e))

    try:
        if _rag_pipeline is not None and getattr(_rag_pipeline.config, "enable_cross_encoder", False):
            from retrieval import get_cross_encoder

            get_cross_encoder()
    except Exception as e:  # noqa: BLE001  # 运行时预热为可选优化，失败仅记录告警，真正查询时会按需重建
        logger.warning("cross_encoder_runtime_warmup_failed", error=str(e))

    return True


def invalidate_rag_runtime() -> None:
    """Drop cached runtime singletons so the next request rebuilds from fresh data."""
    global _rag_pipeline, _embedding_client, _vector_store, _init_failed

    with _init_lock:
        _rag_pipeline = None
        _embedding_client = None
        _vector_store = None
        _init_failed = False


def _build_retrieval_config(options):
    """Build a request-scoped retrieval config without reinitializing the pipeline."""
    from retrieval import RetrievalConfig

    source_caps = default_per_source_caps()
    for source_name, cap in options.per_source_caps.items():
        if source_name in source_caps:
            source_caps[source_name] = cap

    return RetrievalConfig(
        enable_cross_encoder=options.enable_cross_encoder,
        enable_multi_query=options.enable_multi_query,
        enable_global_mode=options.enable_global_mode,
        max_total_candidates=options.max_total_candidates,
        max_context_tokens=options.max_context_tokens,
        vector_top_k=source_caps.get("vector", 2),
        kg_top_k=source_caps.get("kg", 2),
        bm25_top_k=source_caps.get("bm25", 1),
        table_top_k=source_caps.get("table", 1),
        multi_query_top_k=source_caps.get("multi_query", 1),
        per_source_caps=source_caps,
        enabled_sources=options.enabled_sources,
        include_evidence_trace=options.include_evidence_trace,
    )


def _init_rag_pipeline():
    """Lazily initialize the RAG pipeline components."""
    global _rag_pipeline, _embedding_client, _vector_store, _init_failed

    if _rag_pipeline is not None:
        return True
    if _init_failed:
        return False

    with _init_lock:
        if _rag_pipeline is not None:
            return True
        if _init_failed:
            return False

        try:
            from embedding import EmbeddingClient

            embedding_client = EmbeddingClient()
        except Exception as e:  # noqa: BLE001  # 初始化失败即标记不可用并提前返回，错误详情已由日志记录
            logger.warning("embedding_client_init_failed", error=str(e))
            _init_failed = True
            return False

        try:
            from vector_store import VectorStore

            vector_store = VectorStore()
        except Exception as e:  # noqa: BLE001  # 向量库初始化失败降级为无向量能力，其余检索路径继续工作
            logger.warning("vector_store_init_failed", error=str(e))
            vector_store = None

        kg_graph = None
        try:
            from routes.query import _build_kg

            kg_graph = _build_kg()
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        bm25_index = None
        try:
            from index_registry import get_bm25_index, set_bm25_index

            bm25_index = get_bm25_index()
            if bm25_index is None and vector_store is not None:
                rebuilt_bm25 = _build_bm25_index_from_vector_store(vector_store)
                if rebuilt_bm25 is not None:
                    set_bm25_index(rebuilt_bm25)
                    bm25_index = rebuilt_bm25
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        table_index = None
        try:
            from index_registry import get_table_index

            table_index = get_table_index()
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        domain_dict = None
        try:
            from domain_dict import get_domain_dict

            domain_dict = get_domain_dict()
        except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
            pass

        try:
            from retrieval import RetrievalPipeline, RetrievalConfig

            config = RetrievalConfig(
                enable_cross_encoder=DEFAULT_ENABLE_CROSS_ENCODER,
                max_total_candidates=DEFAULT_MAX_TOTAL_CANDIDATES,
                max_context_tokens=DEFAULT_MAX_CONTEXT_TOKENS,
            )
            pipeline = RetrievalPipeline(
                vector_store=vector_store,
                embedding_client=embedding_client,
                kg_graph=kg_graph,
                bm25_index=bm25_index,
                table_index=table_index,
                config=config,
                domain_dict=domain_dict,
            )
        except Exception as e:  # noqa: BLE001  # RAG 管线初始化失败即标记不可用并提前返回，错误详情已由日志记录
            logger.warning("rag_pipeline_init_failed", error=str(e))
            _init_failed = True
            return False

        _embedding_client = embedding_client
        _vector_store = vector_store
        _rag_pipeline = pipeline
        return True


def _generate_scoped_rag(req: QueryRequest, docs: list[dict]):
    """Do not read unpartitioned global indexes for resource-scoped requests."""
    from dataclasses import replace
    from pathlib import Path
    from generator import RAGGenerator, GenerationConfig
    from retrieval import RetrievalPipeline
    from services.document_snapshot import authorized_graph
    from routes.query import KG_DIR

    if req.session_id:
        raise HTTPException(409, "Legacy sessions are not bound to this document scope; start a new query")
    if req.options.enabled_sources is not None and set(req.options.enabled_sources) != {"kg"}:
        raise HTTPException(503, "Requested sources lack verified document isolation; use kg")
    snapshot = authorized_graph(docs, Path(KG_DIR))
    snapshot = snapshot.subgraph([nid for nid, data in snapshot.nodes(data=True)
                                 if data.get("grounding_status") == "grounded"]).copy()
    if snapshot.number_of_nodes() == 0:
        return QueryResponse(query=req.query, answer="没有可用的授权资料。", sources=None,
                             metadata={"status":"no_data", "document_id":req.document_id,
                                       "document_ids":[doc["document_id"] for doc in docs],
                                       "retrieval_scope":"authorized_kg", "enabled_sources":["kg"],
                                       "session_id":None})
    config = replace(_build_retrieval_config(req.options), enabled_sources=("kg",),
                     enable_multi_query=False, enable_cross_encoder=False)
    pipeline = RetrievalPipeline(None, None, kg_graph=snapshot, config=config)
    generation = GenerationConfig(temperature=req.options.temperature,
                                  model=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
                                  api_key=os.getenv("LANGEXTRACT_API_KEY", ""),
                                  base_url=os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"))
    result = RAGGenerator(pipeline, config=generation).generate(
        req.query, max_context_tokens=req.options.max_context_tokens, retrieval_config=config)
    sources = []
    if req.options.include_sources:
        for source in result.get("sources", []):
            ids = [nid for nid in source.get("entity_ids", []) if nid in snapshot]
            properties = {"entity_ids": ids, "document_ids": sorted({snapshot.nodes[nid]["document_id"] for nid in ids})}
            sources.append(SourceNode(node_id=source["chunk_id"], entity_type=source.get("source", "kg"),
                                      label=source.get("text", "")[:100], properties=properties,
                                      page_idx=source.get("page_idx"), bbox_norm=None,
                                      grounding_status="grounded", relevance_score=source.get("score", 0)))
    return QueryResponse(query=req.query, answer=result["answer"][:4000], sources=sources or None,
                         metadata={**result.get("metadata", {}), "document_id": req.document_id,
                                   "document_ids": [doc["document_id"] for doc in docs],
                                   "retrieval_scope": "authorized_kg", "enabled_sources": ["kg"],
                                   "session_id": None})


@router.post("/rag/query")
async def rag_query(req: QueryRequest, request: Request):
    """Enhanced RAG query using the full retrieval pipeline.

    Falls back to KG-only agent mode if RAG pipeline is unavailable.
    """
    if not req.query.strip():
        raise HTTPException(400, detail="Query cannot be empty")
    from services.resource_access import authorized_documents, require_principal, is_admin
    docs = authorized_documents(request, req.document_id)
    if req.document_id or request.headers.get("X-Project-Id") or not is_admin(require_principal(request)):
        return _generate_scoped_rag(req, docs)
    pipeline_ready = _init_rag_pipeline()
    if not pipeline_ready and (req.options.enabled_sources is not None or req.options.include_evidence_trace):
        raise HTTPException(503, detail="RAG pipeline unavailable for explicit enabled_sources; legacy fallback disabled")

    # Increment shared query counter
    import routes
    routes.increment_query_count()

    t0 = time.time()

    # §10.2: Multi-turn conversation context
    conversation = None
    rewritten_query = req.query
    rewrite_reason = None
    conv_sources: list[str] = []
    conv_id = None
    try:
        from conversation import get_conversation_manager, resolve_coreference

        conv_mgr = get_conversation_manager()
        conv = conv_mgr.get_or_create(req.session_id, req.query)
        conv_id = conv.session_id

        # Resolve coreferences if conversation has history
        if len(conv.turns) > 0:
            history = conv.recent_history(3)
            rewritten = resolve_coreference(req.query, history)
            if rewritten != req.query:
                rewritten_query = rewritten
                rewrite_reason = "coreference_resolution"

        conversation = conv
    except Exception as e:  # noqa: BLE001  # 会话上下文构建失败仅记录告警，查询按单轮继续执行
        logger.warning("conversation_init_failed", error=str(e))

    # Try RAG pipeline first
    if not pipeline_ready:
        # Fallback to legacy KG agent
        from routes.query import _get_agent, _invoke_legacy_agent
        agent = _get_agent()
        result = _invoke_legacy_agent(agent, rewritten_query, language=req.options.language)
        messages = result.get("messages", [])
        answer = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "No answer."
        runtime_metadata = result.get("metadata", {})

        return QueryResponse(
            query=req.query,
            answer=answer[:4000],
            sources=None,
            metadata={
                "document_id": req.document_id or "doc_default",
                "model": os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
                "mode": "kg_agent_fallback",
                "duration_ms": int((time.time() - t0) * 1000),
                "session_id": conv_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **runtime_metadata,
            },
        )

    # Use full RAG pipeline with multi-turn support
    from generator import RAGGenerator, GenerationConfig

    gen_config = GenerationConfig(
        temperature=req.options.temperature,
        model=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
        api_key=os.getenv("LANGEXTRACT_API_KEY", ""),
        base_url=os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
    )

    generator = RAGGenerator(_rag_pipeline, config=gen_config)
    retrieval_config = _build_retrieval_config(req.options)

    # Inject conversation history into generation context
    gen_kwargs = {}
    if conversation and len(conversation.turns) > 0:
        gen_kwargs["chat_history"] = conversation.recent_history(3)

    gen_result = generator.generate(
        rewritten_query,
        max_context_tokens=req.options.max_context_tokens,
        retrieval_config=retrieval_config,
        **gen_kwargs,
    )

    # Build source nodes for response
    sources = []
    if req.options.include_sources:
        for s in gen_result.get("sources", []):
            entity_ids = s.get("entity_ids", [])
            if not isinstance(entity_ids, list):
                entity_ids = []
            sources.append(SourceNode(
                node_id=s.get("chunk_id", ""),
                entity_type="chunk",
                label=s.get("text_snippet", "")[:100],
                properties={
                    "source": s.get("source", ""),
                    "score": s.get("score", 0),
                    "section_title": s.get("section_title", ""),
                    "entity_ids": entity_ids,
                    "retrieval_flags": {
                        "multi_query": retrieval_config.enable_multi_query,
                        "global_mode": retrieval_config.enable_global_mode,
                    },
                },
                page_idx=s.get("page_idx"),
                bbox_norm=None,
                grounding_status="grounded",
                relevance_score=s.get("score", 0),
            ))
            conv_sources.append(s.get("chunk_id", ""))

    # §10.2: Save turn to conversation
    if conversation:
        try:
            conv = conv_mgr.append_turn(
                conv_id, req.query, gen_result["answer"],
                rewritten=rewritten_query if rewritten_query != req.query else None,
                rewrite_reason=rewrite_reason,
                sources=conv_sources,
            )
            if conv is None:
                # Session expired, create new
                conversation = conv_mgr.create(req.query)
                conv_mgr.append_turn(conversation.session_id, req.query, gen_result["answer"],
                                     rewritten=rewritten_query if rewritten_query != req.query else None,
                                     rewrite_reason=rewrite_reason,
                                     sources=conv_sources)
                conv_id = conversation.session_id
        except Exception as e:  # noqa: BLE001  # 会话落盘失败仅记录告警，不影响本次查询响应返回
            logger.warning("conversation_save_failed", error=str(e))

    meta = gen_result.get("metadata", {})
    evidence_trace = meta.get("evidence_trace") if req.options.include_evidence_trace else None
    if evidence_trace is not None:
        from copy import deepcopy
        from evidence_trace import answer_stage
        evidence_trace = deepcopy(evidence_trace)
        evidence_trace["answer_stages"].append(answer_stage("api_response_limit", gen_result["answer"], gen_result["answer"][:4000], "4000_char_response_limit"))
        evidence_trace["final_answer"] = gen_result["answer"][:4000]
    degraded_mode = meta.get("degraded_mode")
    if degraded_mode is None and meta.get("rerank_budget_triggered"):
        degraded_mode = "rerank_skipped"
    elif degraded_mode is None and len(meta.get("final_context_chunk_ids", [])) < len(meta.get("pre_rerank_chunk_ids", [])):
        degraded_mode = "candidate_trimmed"

    return QueryResponse(
        query=req.query,
        answer=gen_result["answer"][:4000],
        sources=sources if sources else None,
        metadata={
            "document_id": req.document_id or "doc_default",
            "model": meta.get("model", ""),
            "intent": meta.get("intent", ""),
            "retrieval_ms": meta.get("retrieval_latency_ms", 0),
            "generation_ms": meta.get("generation_latency_ms", 0),
            "duration_ms": meta.get("total_latency_ms", 0),
            "mode": "rag_pipeline",
            "effective_config": meta.get("effective_config"),
            **({"evidence_trace": evidence_trace} if evidence_trace is not None else {}),
            "query_mode": meta.get("query_mode", "local"),
            "has_citations": meta.get("has_citations", False),
            "has_table": meta.get("has_table", False),
            "token_usage": meta.get("token_usage", {}),
            "retrieval_node_ids": meta.get("retrieval_node_ids", []),
            "retrieval_chunk_ids": meta.get("retrieval_chunk_ids", []),
            "pre_rerank_node_ids": meta.get("pre_rerank_node_ids", []),
            "pre_rerank_chunk_ids": meta.get("pre_rerank_chunk_ids", []),
            "final_context_node_ids": meta.get("final_context_node_ids", []),
            "final_context_chunk_ids": meta.get("final_context_chunk_ids", []),
            "path_hit_node_ids": meta.get("path_hit_node_ids", {}),
            "active_recall_paths": meta.get("active_recall_paths", 0),
            "rerank_budget_triggered": meta.get("rerank_budget_triggered", False),
            "rerank_skipped": meta.get("rerank_skipped"),
            "rerank_candidate_count": meta.get("rerank_candidate_count", 0),
            "rerank_max_candidates": meta.get("rerank_max_candidates", 0),
            "rerank_workload_chars": meta.get("rerank_workload_chars", 0),
            "rerank_max_chars": meta.get("rerank_max_chars", 0),
            "degraded_mode": degraded_mode,
            "budget": {
                "max_total_candidates": retrieval_config.max_total_candidates,
                "max_context_tokens": retrieval_config.max_context_tokens,
                "per_source_caps": retrieval_config.per_source_caps,
                "enable_cross_encoder": retrieval_config.enable_cross_encoder,
                "enable_multi_query": retrieval_config.enable_multi_query,
                "enable_global_mode": retrieval_config.enable_global_mode,
                "rerank_budget_ms": retrieval_config.rerank_budget_ms,
                "rerank_max_candidates": retrieval_config.rerank_max_candidates,
                "rerank_high_recall_max_candidates": retrieval_config.rerank_high_recall_max_candidates,
                "rerank_max_chars": retrieval_config.rerank_max_chars,
            },
            "session_id": conv_id,
            "rewritten_query": rewritten_query if rewritten_query != req.query else None,
            "rewrite_reason": rewrite_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.post("/rag/retrieve")
async def rag_retrieve(req: QueryRequest):
    """Chunks-only retrieval for compliance checking — no generation."""
    if not _init_rag_pipeline():
        if req.options.enabled_sources is not None or req.options.include_evidence_trace:
            raise HTTPException(503, detail="RAG pipeline unavailable for explicit enabled_sources")
        return {"chunks": [], "metadata": {"total": 0, "engine_mode": "local", "error": "pipeline not ready"}}

    retrieval_config = _build_retrieval_config(req.options)
    result = _rag_pipeline.retrieve(req.query, retrieval_config=retrieval_config)

    chunks = []
    for c in result.chunks:
        filename = c.metadata.get("filename", c.metadata.get("source_file", "")) if c.metadata else ""
        chunks.append({
            "text": c.text,
            "source_file": filename,
            "relevance_score": round(float(c.score), 4),
        })

    return {"chunks": chunks, "metadata": {"total": len(chunks), "engine_mode": "local",
                                            "effective_config": result.pipeline.get("effective_config"),
                                            **({"evidence_trace": result.pipeline["evidence_trace"]}
                                               if req.options.include_evidence_trace and "evidence_trace" in result.pipeline else {})}}


@router.post("/rag/summarize")
async def rag_summarize(req: QueryRequest, request: Request):
    """Summarization endpoint for weekly reports etc."""
    summarize_prompt = "请用一段简洁的中文总结以下内容要点：\n\n" + req.query
    req.query = summarize_prompt
    return await rag_query(req, request)
