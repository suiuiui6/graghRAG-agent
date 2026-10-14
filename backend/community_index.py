from __future__ import annotations

from collections import Counter
from typing import Any

import networkx as nx


def _tokenize_community_text(text: str) -> list[str]:
    from kg_store import _tokenize_kg_lookup_text

    return _tokenize_kg_lookup_text(text)


def build_community_index(graph: nx.Graph) -> dict[str, Any]:
    """Build lightweight community summary records for global graph retrieval."""
    if graph is None or graph.number_of_nodes() == 0:
        return {
            "communities": [],
            "community_by_id": {},
            "node_to_community": {},
            "token_to_communities": {},
        }

    try:
        communities = list(nx.algorithms.community.greedy_modularity_communities(graph))
    except Exception:  # noqa: BLE001  # 社区发现为可选增强，算法异常时退化为连通分量，不影响索引可用性
        communities = [set(component) for component in nx.connected_components(graph)]

    records: list[dict[str, Any]] = []
    community_by_id: dict[str, dict[str, Any]] = {}
    node_to_community: dict[str, str] = {}
    token_to_communities: dict[str, list[str]] = {}

    for index, nodes in enumerate(communities):
        node_ids = sorted(nodes, key=lambda node_id: str(node_id))
        labels = [
            str(graph.nodes[node_id].get("label", node_id) or node_id)
            for node_id in node_ids[:20]
        ]
        entity_types = Counter(
            str(graph.nodes[node_id].get("entity_type", "unknown") or "unknown")
            for node_id in node_ids
        )
        summary_text = " | ".join(labels[:10])
        record = {
            "community_id": f"c{index:05d}",
            "node_ids": node_ids,
            "size": len(node_ids),
            "top_entity_types": dict(entity_types.most_common(5)),
            "summary_text": summary_text,
        }
        records.append(record)
        community_by_id[record["community_id"]] = record
        for node_id in node_ids:
            node_to_community[node_id] = record["community_id"]
        for token in _tokenize_community_text(
            f"{summary_text} {' '.join(record['top_entity_types'].keys())}"
        ):
            bucket = token_to_communities.setdefault(token, [])
            if record["community_id"] not in bucket:
                bucket.append(record["community_id"])

    return {
        "communities": records,
        "community_by_id": community_by_id,
        "node_to_community": node_to_community,
        "token_to_communities": token_to_communities,
    }


def search_community_records(
    query: str,
    community_index: dict[str, Any],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Score community summaries against a broad query."""
    if limit <= 0:
        return []

    communities = community_index.get("communities", [])
    if not communities:
        return []

    normalized_query = (query or "").strip().lower()
    query_tokens = _tokenize_community_text(query)
    token_map = community_index.get("token_to_communities", {})
    community_by_id = community_index.get("community_by_id", {})
    hit_counts: dict[str, int] = {}
    first_hit_order: dict[str, int] = {}

    for token in query_tokens:
        for community_id in token_map.get(token, []):
            hit_counts[community_id] = hit_counts.get(community_id, 0) + 1
            if community_id not in first_hit_order:
                first_hit_order[community_id] = len(first_hit_order)

    if hit_counts:
        ranked_ids = sorted(
            hit_counts,
            key=lambda community_id: (
                0
                if normalized_query
                and normalized_query in community_by_id[community_id]["summary_text"].lower()
                else 1,
                -hit_counts[community_id],
                -community_by_id[community_id]["size"],
                first_hit_order[community_id],
            ),
        )
        return [
            {**community_by_id[community_id], "score": float(hit_counts[community_id])}
            for community_id in ranked_ids[:limit]
        ]

    fallback = sorted(
        communities,
        key=lambda record: (-record["size"], record["community_id"]),
    )
    return [{**record, "score": 0.0} for record in fallback[:limit]]


def score_community_record(
    query: str,
    entity_types: list[str] | None,
    record: dict[str, Any],
) -> float:
    """Compute a lightweight relevance score for a community summary."""
    normalized_query = (query or "").strip().lower()
    query_tokens = set(_tokenize_community_text(query))
    summary_text = str(record.get("summary_text", "") or "").lower()
    top_entity_types = set((record.get("top_entity_types", {}) or {}).keys())
    score = 0.0

    if normalized_query and normalized_query in summary_text:
        score += 3.0

    for token in query_tokens:
        if token and token in summary_text:
            score += 1.0

    if entity_types:
        score += 0.5 * len(set(entity_types) & top_entity_types)

    return score
