"""KG Query endpoint — §3.2.3. Uses LangGraph Agent + DeepSeek."""

import json, os, threading, time
from datetime import datetime, timezone
from typing import Optional

import networkx as nx
from fastapi import APIRouter, HTTPException
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from models import QueryRequest, QueryResponse, SourceNode

router = APIRouter()

# ---- KG Store ----
G_grounded: Optional[nx.Graph] = None

KG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "kg")
DEFAULT_NODES_PATH = os.path.join(KG_DIR, "nodes.json")
DEFAULT_EDGES_PATH = os.path.join(KG_DIR, "edges.json")


def _load_single_kg(nodes_path: str, edges_path: str, id_prefix: str = "") -> nx.Graph:
    """Load a single KG from nodes.json + edges.json. Optionally prefix node IDs."""
    with open(nodes_path, encoding="utf-8") as f:
        nodes_data = json.load(f)
    with open(edges_path, encoding="utf-8") as f:
        edges_data = json.load(f)

    G = nx.Graph()
    for n in nodes_data["nodes"]:
        nid = id_prefix + n["node_id"]
        G.add_node(nid, entity_type=n["entity_type"], label=n["label"],
                   properties=n.get("properties", {}), page_idx=n.get("page_idx"),
                   bbox_norm=n.get("bbox_norm"), grounding_status=n.get("grounding_status", "ungrounded"),
                   origin_id=n["node_id"])  # keep original ID for reference
    for e in edges_data["edges"]:
        G.add_edge(id_prefix + e["source_node_id"],
                   id_prefix + e["target_node_id"],
                   relation=e.get("relation_type", "connected"))
    return G


def _load_all_kgs() -> nx.Graph:
    """Scan output/kg/ subdirectories for per-document KGs, merge into one graph.
    Falls back to default KG if no subdirectory KGs found.
    """
    merged = nx.Graph()
    kg_dirs = []

    if os.path.isdir(KG_DIR):
        for entry in sorted(os.listdir(KG_DIR)):
            entry_path = os.path.join(KG_DIR, entry)
            if not os.path.isdir(entry_path):
                continue
            n_path = os.path.join(entry_path, "nodes.json")
            e_path = os.path.join(entry_path, "edges.json")
            if os.path.exists(n_path) and os.path.exists(e_path):
                kg_dirs.append((entry, n_path, e_path))

    if kg_dirs:
        for di, (dname, n_path, e_path) in enumerate(kg_dirs):
            prefix = f"d{di}_"
            sub_g = _load_single_kg(n_path, e_path, id_prefix=prefix)
            merged = nx.compose(merged, sub_g)
    elif os.path.exists(DEFAULT_NODES_PATH) and os.path.exists(DEFAULT_EDGES_PATH):
        merged = _load_single_kg(DEFAULT_NODES_PATH, DEFAULT_EDGES_PATH)

    return merged


def _load_kg():
    global G_grounded
    if G_grounded is None:
        full_g = _load_all_kgs()
        G_grounded = _build_kg_from_full(full_g)


def _build_kg_from_full(full_g: nx.Graph) -> Optional[nx.Graph]:
    """Filter full graph to only grounded nodes. Returns None if empty."""
    grounded = full_g.subgraph(
        [n for n, d in full_g.nodes(data=True) if d.get("grounding_status") == "grounded"]
    ).copy()
    if grounded.number_of_nodes() == 0:
        return None
    return grounded


def _build_kg() -> Optional[nx.Graph]:
    """Load KG from disk and return grounded subgraph (no global side effect)."""
    full_g = _load_all_kgs()
    return _build_kg_from_full(full_g)


def _build_agent(g: Optional[nx.Graph]):
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
    G_grounded = new_g
    _agent = new_agent


def _get_model():
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path)
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
        """Search the Knowledge Graph by entity type and optional keyword. Use to find entities like metrics, model components, datasets, methods."""
        results = []
        kw = (keyword or "").lower()
        for nid, data in g.nodes(data=True):
            if entity_type and data["entity_type"] != entity_type: continue
            label = data.get("label", "")
            props = data.get("properties", {})
            if kw and kw not in label.lower() and kw not in " ".join(str(v) for v in props.values()).lower(): continue
            results.append({"node_id": nid, "entity_type": data["entity_type"], "label": label, "properties": props, "page_idx": data.get("page_idx")})
            if len(results) >= max_results: break
        return json.dumps(results, ensure_ascii=False, indent=2) if results else f"No entities found."
    return search_kg_by_type


def _make_neighbors_tool(g: nx.Graph):
    @tool
    def get_entity_neighbors(node_id: str = "", label_keyword: str = "", k_hops: int = 1, max_results: int = 15) -> str:
        """Get neighbors of an entity. Use to explore relationships in the KG."""
        source_id = node_id
        if not source_id and label_keyword:
            kw = label_keyword.lower()
            for nid, data in g.nodes(data=True):
                if kw in data.get("label", "").lower(): source_id = nid; break
        if not source_id or source_id not in g:
            return f"Entity not found."
        ego = nx.ego_graph(g, source_id, radius=k_hops)
        src = g.nodes[source_id]
        neighbors = []
        for nid in ego.nodes():
            if nid == source_id: continue
            nd = g.nodes[nid]
            neighbors.append({"node_id": nid, "entity_type": nd["entity_type"], "label": nd["label"], "relation": g.get_edge_data(source_id, nid, {}).get("relation", "connected")})
        return json.dumps({"source": {"node_id": source_id, "entity_type": src["entity_type"], "label": src["label"]}, "neighbors": neighbors[:max_results]}, ensure_ascii=False, indent=2)
    return get_entity_neighbors


SYSTEM_PROMPT = """You are a Knowledge Graph QA agent. Answer questions about a document by querying its KG.
Use exact text from the source. Cite node IDs and page numbers. Answer in the user's language.
If the KG doesn't have the answer, say so clearly."""


_agent = None
_agent_lock = threading.Lock()


def _get_agent():
    """Get or lazily create the LangGraph agent with double-checked locking."""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _load_kg()
                _agent = _build_agent(G_grounded)
    return _agent


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
        result = agent.invoke({"messages": [("user", req.query)]})
    except Exception as e:
        raise HTTPException(500, detail=f"Agent error: {str(e)}")

    messages = result.get("messages", [])
    answer = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1]) if messages else "No answer."

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
                except:
                    pass

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
        },
    )
