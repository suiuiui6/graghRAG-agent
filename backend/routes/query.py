"""KG Query endpoint — §3.2.3. Uses LangGraph Agent + DeepSeek."""

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import networkx as nx
from fastapi import APIRouter, HTTPException
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from kg_store import (
    bounded_neighbor_lookup,
    get_kg_lookup_indexes,
    lookup_kg_label_nodes,
    load_all_kg_graphs,
    lookup_kg_nodes,
)
from models import QueryRequest, QueryResponse, SourceNode
from errors import ErrorCode, ErrorContext, UpstreamUnavailableError
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# ---- KG Store ----
G_grounded: nx.Graph | None = None

KG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "kg")
DEFAULT_NODES_PATH = os.path.join(KG_DIR, "nodes.json")
DEFAULT_EDGES_PATH = os.path.join(KG_DIR, "edges.json")
LEGACY_QUERY_TOOL_LIMIT = 8
MAX_LEGACY_NEIGHBOR_FANOUT = 10
LEGACY_QUERY_RECURSION_LIMIT = max(
    4,
    int(os.getenv("LEGACY_QUERY_RECURSION_LIMIT", "16")),
)


def _load_all_kgs() -> nx.Graph:
    """Load KGs through the version-aware kg_store path."""
    return load_all_kg_graphs(base_dir=Path(KG_DIR))


def _load_kg():
    global G_grounded
    if G_grounded is None:
        full_g = _load_all_kgs()
        G_grounded = _build_kg_from_full(full_g)


def _build_kg_from_full(full_g: nx.Graph) -> nx.Graph | None:
    """Filter full graph to only grounded nodes. Returns None if empty."""
    grounded = full_g.subgraph(
        [n for n, d in full_g.nodes(data=True) if d.get("grounding_status") == "grounded"]
    ).copy()
    if grounded.number_of_nodes() == 0:
        return None
    get_kg_lookup_indexes(grounded)
    return grounded


def _build_kg() -> nx.Graph | None:
    """Load KG from disk and return grounded subgraph (no global side effect)."""
    full_g = _load_all_kgs()
    return _build_kg_from_full(full_g)


def _build_agent(g: nx.Graph | None):
    """Create a LangGraph agent from a given KG graph (no global side effect)."""
    if g is not None and g.number_of_nodes() > 0:
        tools = [_make_search_tool(g), _make_neighbors_tool(g)]
    else:
        G_empty = nx.Graph()
        G_empty.add_node("_placeholder", entity_type="placeholder", label="No data",
                         properties={}, page_idx=None, bbox_norm=None, grounding_status="ungrounded")
        tools = [_make_search_tool(G_empty), _make_neighbors_tool(G_empty)]
    return create_agent(model=_get_model(), tools=tools, system_prompt=SYSTEM_PROMPT)


def reload_kg():
    """Hot-reload the KG from disk (called after indexing completes). Atomically swaps globals."""
    global G_grounded, _agent
    new_g = _build_kg()
    new_agent = _build_agent(new_g)
    with _kg_swap_lock:
        G_grounded = new_g
        _agent = new_agent
    try:
        from routes.rag_query import invalidate_rag_runtime

        invalidate_rag_runtime()
    except Exception:  # noqa: S110, BLE001  # 可选依赖或产物缺失时降级为跳过，缺失本身已由调用方判定
        pass


def _get_model():
    return ChatOpenAI(
        model=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
        base_url=os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("LANGEXTRACT_API_KEY", ""),
        temperature=0.0, timeout=120,
    )


# ---- Tools ----
def _make_search_tool(g: nx.Graph):
    @tool
    def search_kg_by_type(entity_type: str = "", keyword: str = "", max_results: int = 15) -> str:
        """Legacy, non-primary KG search. Uses indexed lookup with a strict result cap."""
        hard_limit = max(1, min(max_results, LEGACY_QUERY_TOOL_LIMIT))
        matches = lookup_kg_nodes(
            g,
            entity_types=[entity_type] if entity_type else None,
            keyword=keyword,
            limit=hard_limit,
        )
        results = []
        for nid, data in matches:
            results.append({
                "node_id": nid,
                "entity_type": data["entity_type"],
                "label": data["label"],
                "properties": data.get("properties", {}),
                "page_idx": data.get("page_idx"),
            })
        return json.dumps(results, ensure_ascii=False, indent=2) if results else "No entities found."
    return search_kg_by_type


def _make_neighbors_tool(g: nx.Graph):
    @tool
    def get_entity_neighbors(node_id: str = "", label_keyword: str = "", k_hops: int = 1, max_results: int = 15) -> str:
        """Legacy, non-primary KG neighbor lookup for targeted follow-up exploration."""
        indexes = get_kg_lookup_indexes(g)
        source_id = node_id
        if not source_id and label_keyword:
            label_matches = lookup_kg_label_nodes(
                g,
                keyword=label_keyword,
                limit=1,
                indexes=indexes,
            )
            if label_matches:
                source_id = label_matches[0][0]
            if not source_id:
                matches = lookup_kg_nodes(g, keyword=label_keyword, limit=1, indexes=indexes)
                if matches:
                    source_id = matches[0][0]
        if not source_id or source_id not in g:
            return "Entity not found."
        src = g.nodes[source_id]
        neighbors = bounded_neighbor_lookup(
            g,
            source_id,
            k_hops=k_hops,
            fanout=MAX_LEGACY_NEIGHBOR_FANOUT,
            indexes=indexes,
        )
        hard_limit = max(1, min(max_results, LEGACY_QUERY_TOOL_LIMIT))
        return json.dumps({"source": {"node_id": source_id, "entity_type": src["entity_type"], "label": src["label"]}, "neighbors": neighbors[:hard_limit]}, ensure_ascii=False, indent=2)
    return get_entity_neighbors


SYSTEM_PROMPT = """You are a Knowledge Graph QA agent. Answer questions about a document by querying its KG.
Use exact text from the source. Cite node IDs and page numbers. Answer in the user's language.
If the KG doesn't have the answer, say so clearly.

Tool-use policy:
- Use at most 6 tool calls total unless a direct contradiction must be resolved.
- Start with one precise `search_kg_by_type` query using the user's original language.
- Do not repeat the same search with paraphrases, translations, or near-duplicate keywords.
- Use `get_entity_neighbors` only for the 1-2 most relevant nodes returned by search.
- Do not explore exhaustively. Once you have enough evidence to answer, stop calling tools and answer.
- If a search result already contains the needed metric, method, or definition, answer directly instead of continuing to browse neighbors.
- If evidence is incomplete after one search and one neighbor lookup, state the limitation instead of continuing broad search."""


_agent = None
_agent_lock = threading.Lock()
_kg_swap_lock = threading.Lock()


def _get_agent():
    """Get or lazily create the LangGraph agent with double-checked locking."""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                with _kg_swap_lock:
                    _load_kg()
                    _agent = _build_agent(G_grounded)
    return _agent


def _legacy_step_limit_answer(language: str) -> str:
    if language == "ch":
        return (
            "未能在遗留 KG 查询步数预算内完成检索。"
            "请缩小问题范围，或改用 `/api/v1/rag/query` 获取主 GraphRAG 结果。"
        )
    if language == "ja":
        return (
            "レガシー KG クエリのステップ上限内で回答を完了できませんでした。"
            "質問を絞るか、主系統の `/api/v1/rag/query` を利用してください。"
        )
    return (
        "The legacy KG query agent could not finish within its step budget. "
        "Narrow the question or use `/api/v1/rag/query` for the primary GraphRAG path."
    )


def _invoke_legacy_agent(agent, user_query: str, *, language: str = "en") -> dict:
    try:
        return agent.invoke(
            {"messages": [("user", user_query)]},
            config={"recursion_limit": LEGACY_QUERY_RECURSION_LIMIT},
        )
    except GraphRecursionError:
        return {
            "messages": [AIMessage(content=_legacy_step_limit_answer(language))],
            "metadata": {
                "step_limited": True,
                "error_code": "GRAPH_RECURSION_LIMIT",
                "recursion_limit": LEGACY_QUERY_RECURSION_LIMIT,
            },
        }


# ---- Endpoint ----
@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(400, detail="Query cannot be empty")

    # Increment shared query counter for health stats
    import routes
    routes.increment_query_count()

    t0 = time.time()
    agent = _get_agent()

    try:
        result = _invoke_legacy_agent(agent, req.query, language=req.options.language)
    except Exception as e:
        raise UpstreamUnavailableError(
            "KG 查询 Agent 调用失败",
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            context=ErrorContext(provider="deepseek", retryable=True),
        ) from e

    messages = result.get("messages", [])
    answer = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "No answer."
    runtime_metadata = result.get("metadata", {})

    # Extract sources from tool calls and answer text
    sources = []
    if req.options.include_sources and G_grounded is not None and G_grounded.number_of_nodes() > 0:
        import re
        node_ids = set()

        # Extract node IDs from tool call results
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # This is a tool call message
                continue
            if hasattr(msg, "content") and isinstance(msg.content, str):
                # Try to parse JSON from tool results
                try:
                    content_data = json.loads(msg.content)
                    if isinstance(content_data, list):
                        for item in content_data:
                            if isinstance(item, dict) and "node_id" in item:
                                node_ids.add(item["node_id"])
                    elif isinstance(content_data, dict):
                        if "node_id" in content_data:
                            node_ids.add(content_data["node_id"])
                        if "neighbors" in content_data:
                            for neighbor in content_data["neighbors"]:
                                if isinstance(neighbor, dict) and "node_id" in neighbor:
                                    node_ids.add(neighbor["node_id"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    # 响应体非 JSON / 结构不符时跳过该来源提取，不影响主答案
                    logger.debug("source_extraction_skipped", exc_info=True)

        # Also extract from answer text (fallback)
        node_ids.update(re.findall(r'd\d+_[a-zA-Z0-9_]+', answer))

        # Build source list
        for nid in list(node_ids)[:15]:
            if nid in G_grounded:
                d = G_grounded.nodes[nid]
                sources.append(SourceNode(
                    node_id=nid, entity_type=d["entity_type"], label=d["label"][:100],
                    properties=d.get("properties", {}), page_idx=d.get("page_idx"),
                    bbox_norm=d.get("bbox_norm"), grounding_status=d.get("grounding_status", "ungrounded"),
                    relevance_score=0.9,
                ))

    return QueryResponse(
        query=req.query,
        answer=answer[:4000],
        sources=sources if sources else None,
        metadata={
            "document_id": req.document_id or "doc_a1b2c3d4",
            "model": os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
            "tool_calls": len([m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]),
            "duration_ms": int((time.time() - t0) * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "legacy_agent_recursion_limit": LEGACY_QUERY_RECURSION_LIMIT,
            **runtime_metadata,
        },
    )
