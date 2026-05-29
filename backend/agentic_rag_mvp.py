#!/usr/bin/env python3
"""
Agentic-RAG MVP: KG-based QA with LangGraph + DeepSeek v4 pro

Pipeline:
  nodes.json + edges.json → NetworkX Graph → LangChain Tools
  → LangGraph Agent (DeepSeek v4 pro) → KG-powered answers

Spec: follows D:\graghRAG-agent\langextract\docs\bridge-pipeline-specification-v1.0.md

Usage:
  source D:/graghRAG-agent/langextract/.venv/Scripts/activate
  python agentic_rag_mvp.py
"""

import json
import os
import sys
from datetime import datetime
from typing import Annotated

import networkx as nx
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# ============================================================
# 0. Config
# ============================================================
KG_DIR = os.path.join(os.path.dirname(__file__), "output", "kg")
NODES_PATH = os.path.join(KG_DIR, "nodes.json")
EDGES_PATH = os.path.join(KG_DIR, "edges.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"  # deepseek-chat for MVP; v4-pro needs thinking_mode handling
V4_PRO_MODE = False

# ============================================================
# 1. Load KG data → NetworkX Graph
# ============================================================
print("=" * 60)
print("  Agentic-RAG MVP: KG-based QA")
print(f"  Model: {MODEL_NAME} via {DEEPSEEK_BASE_URL}")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

print(f"\n[1] Loading Knowledge Graph...")
with open(NODES_PATH, "r", encoding="utf-8") as f:
    nodes_data = json.load(f)
with open(EDGES_PATH, "r", encoding="utf-8") as f:
    edges_data = json.load(f)

G = nx.Graph()

# Add nodes
type_counts = {}
grounded_count = 0
for node in nodes_data["nodes"]:
    G.add_node(
        node["node_id"],
        entity_type=node["entity_type"],
        label=node["label"],
        properties=node.get("properties", {}),
        page_idx=node.get("page_idx"),
        bbox_norm=node.get("bbox_norm"),
        grounding_status=node.get("grounding_status", "ungrounded"),
    )
    t = node["entity_type"]
    type_counts[t] = type_counts.get(t, 0) + 1
    if node.get("grounding_status") == "grounded":
        grounded_count += 1

# Add edges
for edge in edges_data["edges"]:
    G.add_edge(
        edge["source_node_id"],
        edge["target_node_id"],
        relation=edge["relation_type"],
        **edge.get("properties", {}),
    )

# Filter grounded-only subgraph
G_grounded = G.subgraph(
    [n for n, d in G.nodes(data=True) if d.get("grounding_status") == "grounded"]
).copy()

print(f"  Nodes: {G.number_of_nodes()} (grounded: {G_grounded.number_of_nodes()})")
print(f"  Edges: {G.number_of_edges()} (grounded: {G_grounded.number_of_edges()})")
print(f"  Types: {len(type_counts)}")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:8]:
    print(f"    {t:25s} {c:4d}")

# ============================================================
# 2. Define LangChain Tools
# ============================================================

@tool
def search_kg_by_type(
    entity_type: str = "",
    keyword: str = "",
    max_results: int = 15,
) -> str:
    """
    Search the document's Knowledge Graph by entity type and optional keyword.
    Use this to find entities of a specific type (e.g., 'metric', 'model_component',
    'dataset', 'method', 'definition', 'claim', 'reference', 'paper_metadata',
    'section_header', 'equation').

    Args:
        entity_type: Filter by entity type. Leave empty to search all types.
        keyword: Optional keyword to filter labels/properties (case-insensitive).
        max_results: Maximum number of results (default 15).

    Returns:
        JSON string with matching entities including node_id, label, properties, page_idx.
    """
    results = []
    kw = keyword.lower() if keyword else ""

    for nid, data in G_grounded.nodes(data=True):
        if entity_type and data["entity_type"] != entity_type:
            continue
        label = data.get("label", "")
        props = data.get("properties", {})
        props_str = " ".join(str(v) for v in props.values())

        if kw and kw not in label.lower() and kw not in props_str.lower():
            continue

        results.append({
            "node_id": nid,
            "entity_type": data["entity_type"],
            "label": label,
            "properties": props,
            "page_idx": data.get("page_idx"),
        })

        if len(results) >= max_results:
            break

    if not results:
        return f"No entities found for entity_type='{entity_type}', keyword='{keyword}'"

    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def get_entity_neighbors(
    node_id: str = "",
    label_keyword: str = "",
    k_hops: int = 1,
    max_results: int = 15,
) -> str:
    """
    Get the neighbor entities (connected nodes) for a given entity in the Knowledge Graph.
    Use this to explore relationships and find related concepts.

    Args:
        node_id: Exact node_id (e.g., 'n0001'). If empty, find by label_keyword.
        label_keyword: Find entity by matching label, then get its neighbors.
        k_hops: Number of hops to expand. 1 = direct neighbors, 2 = neighbors of neighbors.
        max_results: Maximum neighbor nodes to return.

    Returns:
        JSON string with the source node, its neighbors, and connecting relations.
    """
    # Find source node
    source_id = node_id
    if not source_id and label_keyword:
        kw = label_keyword.lower()
        for nid, data in G_grounded.nodes(data=True):
            if kw in data.get("label", "").lower():
                source_id = nid
                break

    if not source_id or source_id not in G_grounded:
        return f"Entity not found: node_id='{node_id}', label_keyword='{label_keyword}'"

    # k-hop neighborhood
    ego = nx.ego_graph(G_grounded, source_id, radius=k_hops)
    source_data = G_grounded.nodes[source_id]

    neighbors = []
    for nid in ego.nodes():
        if nid == source_id:
            continue
        nd = G_grounded.nodes[nid]
        edge_data = G_grounded.get_edge_data(source_id, nid) or {}
        neighbors.append({
            "node_id": nid,
            "entity_type": nd["entity_type"],
            "label": nd["label"],
            "relation": edge_data.get("relation", "connected"),
        })

    neighbors = neighbors[:max_results]

    return json.dumps({
        "source": {
            "node_id": source_id,
            "entity_type": source_data["entity_type"],
            "label": source_data["label"],
            "properties": source_data.get("properties", {}),
            "page_idx": source_data.get("page_idx"),
        },
        "neighbors_count": len(neighbors),
        "neighbors": neighbors,
        "k_hops": k_hops,
    }, ensure_ascii=False, indent=2)


@tool
def get_entity_detail(node_id: str) -> str:
    """
    Get full details of a specific Knowledge Graph entity, including all properties
    and direct relationships.

    Args:
        node_id: The node identifier (e.g., 'n0001', 'n0150').

    Returns:
        JSON string with full entity data and connected edges.
    """
    if node_id not in G_grounded:
        # Try in full graph
        if node_id in G:
            data = G.nodes[node_id]
        else:
            return f"Entity '{node_id}' not found in KG."
    else:
        data = G_grounded.nodes[node_id]

    # Get edges
    edges = []
    for neighbor in G_grounded.neighbors(node_id):
        edge_data = G_grounded.get_edge_data(node_id, neighbor) or {}
        nd = G_grounded.nodes[neighbor]
        edges.append({
            "target_node_id": neighbor,
            "target_label": nd["label"][:80],
            "target_type": nd["entity_type"],
            "relation": edge_data.get("relation", "connected"),
        })

    return json.dumps({
        "node_id": node_id,
        "entity_type": data["entity_type"],
        "label": data["label"],
        "properties": data.get("properties", {}),
        "page_idx": data.get("page_idx"),
        "grounding_status": data.get("grounding_status"),
        "relationships": edges[:10],
    }, ensure_ascii=False, indent=2)


@tool
def get_kg_statistics() -> str:
    """
    Get overall statistics of the Knowledge Graph: node count, entity type distribution,
    edge count, relation type distribution, and grounding rate.

    Returns:
        JSON string with KG statistics.
    """
    node_counts = {}
    grounded = 0
    for n, d in G.nodes(data=True):
        t = d["entity_type"]
        node_counts[t] = node_counts.get(t, 0) + 1
        if d.get("grounding_status") == "grounded":
            grounded += 1

    edge_relations = {}
    for u, v, d in G.edges(data=True):
        r = d.get("relation", "unknown")
        edge_relations[r] = edge_relations.get(r, 0) + 1

    return json.dumps({
        "total_nodes": G.number_of_nodes(),
        "grounded_nodes": grounded,
        "ungrounded_nodes": G.number_of_nodes() - grounded,
        "grounding_rate": f"{grounded / G.number_of_nodes() * 100:.1f}%",
        "total_edges": G.number_of_edges(),
        "entity_type_distribution": dict(sorted(node_counts.items(), key=lambda x: -x[1])),
        "relation_type_distribution": dict(sorted(edge_relations.items(), key=lambda x: -x[1])),
    }, ensure_ascii=False, indent=2)


# ============================================================
# 3. Build LangGraph Agent
# ============================================================

TOOLS = [search_kg_by_type, get_entity_neighbors, get_entity_detail, get_kg_statistics]

# DeepSeek via OpenAI Compatible endpoint
model = ChatOpenAI(
    model=MODEL_NAME,
    base_url=DEEPSEEK_BASE_URL,
    api_key=DEEPSEEK_API_KEY,
    temperature=0.0,
    timeout=120,
)

SYSTEM_PROMPT = """\
You are a Knowledge Graph QA agent. You answer questions about an academic paper
by querying its Knowledge Graph.

The KG was built by the BridgePipeline (MinerU → LangExtract) and contains
entities with these types:
  - paper_metadata: title, authors, affiliations, venue
  - section_header: chapter/section headings
  - model_component: model parts (layers, mechanisms, modules)
  - metric: quantitative results (scores, percentages, measurements)
  - dataset: datasets and benchmarks
  - method: techniques, algorithms, training strategies
  - definition: explicitly defined concepts
  - equation: mathematical formulas
  - reference: citations to other works
  - claim: key findings and conclusions

Rules:
1. Always use the tools to search the KG — do NOT guess or make up answers.
2. Start with search_kg_by_type to find relevant entities.
3. Use get_entity_neighbors to explore relationships.
4. Use get_entity_detail for full entity information.
5. Answer in the user's language (Chinese or English).
6. Cite the specific node IDs and page numbers from the KG in your answer.
7. If the KG doesn't contain the information, say so clearly.
"""

agent = create_agent(
    model=model,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)

print(f"\n[2] Agent created with {len(TOOLS)} tools:")
for t in TOOLS:
    print(f"    - {t.name}: {t.description.split(chr(10))[0][:80]}...")


# ============================================================
# 4. Run test queries
# ============================================================

TEST_QUERIES = [
    "What is the title of this paper and who are the authors?",
    "What BLEU scores did the Transformer achieve and on which datasets?",
    "What are the key components of the Transformer model architecture?",
    "What regularization methods were used during training?",
    "How many entities are in the Knowledge Graph and what types?",
]


def run_query(agent, query: str, idx: int):
    print(f"\n{'─' * 60}")
    print(f"  Query {idx}: {query}")
    print(f"{'─' * 60}")
    try:
        result = agent.invoke({"messages": [("user", query)]})
        # Extract final answer from messages
        messages = result.get("messages", [])
        final_msg = messages[-1] if messages else None
        if final_msg:
            content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
            # Trim for display
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            print(f"\n{content}")
        else:
            print("[No response]")
    except Exception as e:
        print(f"\n[ERROR] {e}")


# ============================================================
# Main
# ============================================================

def main():
    print(f"\n[3] Running {len(TEST_QUERIES)} test queries...")

    for i, q in enumerate(TEST_QUERIES, 1):
        run_query(agent, q, i)

    print(f"\n{'=' * 60}")
    print(f"  Agentic-RAG MVP Complete")
    print(f"  KG: {G_grounded.number_of_nodes()} grounded nodes, "
          f"{G_grounded.number_of_edges()} edges")
    print(f"  Model: {MODEL_NAME}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
