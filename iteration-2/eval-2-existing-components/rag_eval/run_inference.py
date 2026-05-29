"""
RAG inference runner — 跑 ground truth 上的 50 题，保存所有原始日志.

输出 raw_runs.jsonl，每行一条:
{
  qid, query, category,
  retrieved_node_ids: [...],      # 从 tool call 结果中正则提取
  tool_calls: [{name, args, result_preview}, ...],
  num_tool_calls,
  final_answer,
  latency_ms,
  tokens: {input, output, total},
  error
}

NOTE: 该脚本直接构建 LangGraph agent (不通过 backend HTTP)，
      原因是 backend 未运行，且直接调用更易拿到结构化中间结果。
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

ROOT = Path(r"D:/graghRAG-agent")
KG_DIR = ROOT / "backend" / "output" / "kg" / "doc_ingest_232e1611"
EVAL_DIR = ROOT / "iteration-2" / "eval-2-existing-components" / "rag_eval"
GT_PATH = EVAL_DIR / "ground_truth.json"
OUT_PATH = EVAL_DIR / "raw_runs.jsonl"
LOG_PATH = EVAL_DIR / "run.log"

load_dotenv(ROOT / "backend" / ".env")
DEEPSEEK_API_KEY = os.environ.get("LANGEXTRACT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise SystemExit("Missing DEEPSEEK API key (LANGEXTRACT_API_KEY or DEEPSEEK_API_KEY)")

# ---- Build KG (mirror backend/agentic_rag_mvp.py) -----------------------------
import networkx as nx
from langchain.tools import tool
from langchain_openai import ChatOpenAI

with open(KG_DIR / "nodes.json", "r", encoding="utf-8") as f:
    nodes_data = json.load(f)
with open(KG_DIR / "edges.json", "r", encoding="utf-8") as f:
    edges_data = json.load(f)

G = nx.Graph()
for node in nodes_data["nodes"]:
    G.add_node(node["node_id"], entity_type=node["entity_type"], label=node["label"],
               properties=node.get("properties", {}), page_idx=node.get("page_idx"),
               bbox_norm=node.get("bbox_norm"),
               grounding_status=node.get("grounding_status", "ungrounded"))
for edge in edges_data["edges"]:
    G.add_edge(edge["source_node_id"], edge["target_node_id"],
               relation=edge["relation_type"], **edge.get("properties", {}))

G_grounded = G.subgraph(
    [n for n, d in G.nodes(data=True) if d.get("grounding_status") == "grounded"]
).copy()

print(f"[KG] nodes={G.number_of_nodes()} grounded={G_grounded.number_of_nodes()} edges={G.number_of_edges()}")

# ---- Tools (copy exactly from backend) ---------------------------------------
@tool
def search_kg_by_type(entity_type: str = "", keyword: str = "", max_results: int = 15) -> str:
    """Search the document's Knowledge Graph by entity type and optional keyword."""
    results = []
    kw = keyword.lower() if keyword else ""
    for nid, data in G_grounded.nodes(data=True):
        if entity_type and data["entity_type"] != entity_type:
            continue
        label = data.get("label", "")
        props_str = " ".join(str(v) for v in data.get("properties", {}).values())
        if kw and kw not in label.lower() and kw not in props_str.lower():
            continue
        results.append({"node_id": nid, "entity_type": data["entity_type"],
                        "label": label, "properties": data.get("properties", {}),
                        "page_idx": data.get("page_idx")})
        if len(results) >= max_results:
            break
    return json.dumps(results, ensure_ascii=False) if results else \
        f"No entities found for entity_type='{entity_type}', keyword='{keyword}'"

@tool
def get_entity_neighbors(node_id: str = "", label_keyword: str = "",
                         k_hops: int = 1, max_results: int = 15) -> str:
    """Get the neighbor entities for a given KG entity."""
    source_id = node_id
    if not source_id and label_keyword:
        kw = label_keyword.lower()
        for nid, data in G_grounded.nodes(data=True):
            if kw in data.get("label", "").lower():
                source_id = nid
                break
    if not source_id or source_id not in G_grounded:
        return f"Entity not found: node_id='{node_id}', label_keyword='{label_keyword}'"
    ego = nx.ego_graph(G_grounded, source_id, radius=k_hops)
    src = G_grounded.nodes[source_id]
    neighbors = []
    for nid in ego.nodes():
        if nid == source_id:
            continue
        nd = G_grounded.nodes[nid]
        ed = G_grounded.get_edge_data(source_id, nid) or {}
        neighbors.append({"node_id": nid, "entity_type": nd["entity_type"],
                          "label": nd["label"], "relation": ed.get("relation", "connected")})
    return json.dumps({
        "source": {"node_id": source_id, "label": src["label"], "entity_type": src["entity_type"],
                   "page_idx": src.get("page_idx")},
        "neighbors_count": len(neighbors[:max_results]),
        "neighbors": neighbors[:max_results], "k_hops": k_hops,
    }, ensure_ascii=False)

@tool
def get_entity_detail(node_id: str) -> str:
    """Get full details of a specific KG entity."""
    if node_id not in G_grounded:
        if node_id in G:
            data = G.nodes[node_id]
        else:
            return f"Entity '{node_id}' not found in KG."
    else:
        data = G_grounded.nodes[node_id]
    edges = []
    if node_id in G_grounded:
        for nb in G_grounded.neighbors(node_id):
            ed = G_grounded.get_edge_data(node_id, nb) or {}
            nd = G_grounded.nodes[nb]
            edges.append({"target_node_id": nb, "target_label": nd["label"][:80],
                          "target_type": nd["entity_type"],
                          "relation": ed.get("relation", "connected")})
    return json.dumps({
        "node_id": node_id, "entity_type": data["entity_type"], "label": data["label"],
        "properties": data.get("properties", {}), "page_idx": data.get("page_idx"),
        "grounding_status": data.get("grounding_status"),
        "relationships": edges[:10],
    }, ensure_ascii=False)

@tool
def get_kg_statistics() -> str:
    """Get overall statistics of the Knowledge Graph."""
    nc = {}; grounded = 0
    for n, d in G.nodes(data=True):
        t = d["entity_type"]; nc[t] = nc.get(t, 0) + 1
        if d.get("grounding_status") == "grounded":
            grounded += 1
    ec = {}
    for u, v, d in G.edges(data=True):
        r = d.get("relation", "unknown"); ec[r] = ec.get(r, 0) + 1
    return json.dumps({
        "total_nodes": G.number_of_nodes(), "grounded_nodes": grounded,
        "total_edges": G.number_of_edges(),
        "entity_type_distribution": dict(sorted(nc.items(), key=lambda x: -x[1])),
        "relation_type_distribution": dict(sorted(ec.items(), key=lambda x: -x[1])),
    }, ensure_ascii=False)

# ---- Agent --------------------------------------------------------------------
from langchain.agents import create_agent

TOOLS = [search_kg_by_type, get_entity_neighbors, get_entity_detail, get_kg_statistics]
model = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com",
                   api_key=DEEPSEEK_API_KEY, temperature=0.0, timeout=120)

SYSTEM_PROMPT = """You are a Knowledge Graph QA agent. You answer questions about an academic paper by querying its Knowledge Graph.

The KG was built by the BridgePipeline (MinerU -> LangExtract) and contains entities with these types:
  - paper_metadata, section_header, model_component, metric, dataset, method, definition, equation, reference, claim

Rules:
1. Always use the tools to search the KG -- do NOT guess or make up answers.
2. Start with search_kg_by_type to find relevant entities.
3. Use get_entity_neighbors to explore relationships.
4. Use get_entity_detail for full entity information.
5. Answer in the user's language (Chinese or English).
6. Cite the specific node IDs and page numbers from the KG in your answer.
7. If the KG doesn't contain the information, say so clearly.
"""

agent = create_agent(model=model, tools=TOOLS, system_prompt=SYSTEM_PROMPT)

# ---- Helpers ------------------------------------------------------------------
NODE_ID_RE = re.compile(r"\bn\d{4}\b")

def extract_node_ids_from_text(s: str) -> list[str]:
    if not s:
        return []
    return sorted(set(NODE_ID_RE.findall(s)))

def serialize_tool_calls(messages) -> tuple[list, set[str]]:
    """Extract tool calls + all node_ids that appeared in tool results."""
    calls = []
    retrieved = set()
    for m in messages:
        msg_type = type(m).__name__
        if msg_type == "AIMessage" and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                calls.append({"phase": "request", "name": tc["name"], "args": tc.get("args", {})})
        elif msg_type == "ToolMessage":
            content = m.content if hasattr(m, "content") else str(m)
            preview = content[:500] if isinstance(content, str) else str(content)[:500]
            tname = getattr(m, "name", "?")
            calls.append({"phase": "result", "name": tname, "result_preview": preview})
            retrieved.update(extract_node_ids_from_text(content if isinstance(content, str) else str(content)))
    return calls, retrieved

def extract_tokens(messages) -> dict:
    """Aggregate token usage from all AIMessages."""
    tin = tout = ttotal = 0
    for m in messages:
        if type(m).__name__ == "AIMessage":
            um = getattr(m, "usage_metadata", None) or {}
            if um:
                tin += um.get("input_tokens", 0)
                tout += um.get("output_tokens", 0)
                ttotal += um.get("total_tokens", 0)
            else:
                rm = getattr(m, "response_metadata", {}) or {}
                tu = rm.get("token_usage", {}) or rm.get("usage", {})
                tin += tu.get("prompt_tokens", 0) or tu.get("input_tokens", 0)
                tout += tu.get("completion_tokens", 0) or tu.get("output_tokens", 0)
                ttotal += tu.get("total_tokens", 0)
    return {"input": tin, "output": tout, "total": ttotal}

# ---- Main loop ----------------------------------------------------------------
def main():
    gt = json.load(open(GT_PATH, "r", encoding="utf-8"))
    qs = gt["questions"]
    print(f"[GT] loaded {len(qs)} questions")

    logf = open(LOG_PATH, "w", encoding="utf-8")
    logf.write(f"=== RUN {datetime.now().isoformat()} ===\n")

    outf = open(OUT_PATH, "w", encoding="utf-8")

    for i, q in enumerate(qs, 1):
        qid = q["qid"]
        query = q["question"]
        print(f"\n[{i:02d}/{len(qs)}] {qid} ({q['category']}) {query[:60]}")
        logf.write(f"\n--- {qid} {q['category']} ---\nQ: {query}\n")
        logf.flush()

        record = {
            "qid": qid, "category": q["category"], "query": query,
            "should_refuse": q.get("should_refuse", False),
            "expected_node_ids": q.get("expected_node_ids", []),
            "retrieved_node_ids": [],
            "tool_calls": [], "num_tool_calls": 0,
            "final_answer": "", "answer_node_ids": [],
            "latency_ms": 0, "tokens": {"input": 0, "output": 0, "total": 0},
            "error": None, "timestamp": datetime.now().isoformat(),
        }
        t0 = time.time()
        try:
            result = agent.invoke({"messages": [("user", query)]})
            messages = result.get("messages", [])
            calls, retrieved = serialize_tool_calls(messages)
            final = messages[-1] if messages else None
            answer = final.content if final and hasattr(final, "content") else ""
            record["tool_calls"] = calls
            record["num_tool_calls"] = sum(1 for c in calls if c["phase"] == "request")
            record["retrieved_node_ids"] = sorted(retrieved)
            record["final_answer"] = answer
            record["answer_node_ids"] = extract_node_ids_from_text(answer)
            record["tokens"] = extract_tokens(messages)
        except Exception as e:
            record["error"] = f"{type(e).__name__}: {e}"
            logf.write(f"ERROR: {record['error']}\n{traceback.format_exc()}\n")
            print(f"   [ERROR] {record['error']}")
        record["latency_ms"] = int((time.time() - t0) * 1000)

        outf.write(json.dumps(record, ensure_ascii=False) + "\n")
        outf.flush()

        ans_preview = (record["final_answer"] or "")[:120].replace("\n", " ")
        print(f"   tool_calls={record['num_tool_calls']} retrieved={len(record['retrieved_node_ids'])} "
              f"tokens={record['tokens']['total']} latency={record['latency_ms']}ms")
        print(f"   ans: {ans_preview}")
        logf.write(f"tool_calls={record['num_tool_calls']} retrieved={record['retrieved_node_ids']}\n"
                   f"latency_ms={record['latency_ms']} tokens={record['tokens']}\n"
                   f"answer: {record['final_answer'][:400]}\n")
        logf.flush()

    outf.close()
    logf.close()
    print(f"\nDONE -> {OUT_PATH}")
    print(f"LOG -> {LOG_PATH}")

if __name__ == "__main__":
    main()
