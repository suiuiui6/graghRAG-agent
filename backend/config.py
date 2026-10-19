"""
Global configuration center — §7.2 of rag-engineering-blueprint-v1.0.

Single source of truth for entity types, query intents, relation types,
and all tunable parameters. All modules import from here instead of
scattering hardcoded strings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from source_control import normalize_enabled_sources


def non_thinking_options(model: str) -> dict:
    """HTTP body fields for DeepSeek models whose default enables thinking."""
    if model == "deepseek-flash" or model.startswith("deepseek-v4"):
        return {"thinking": {"type": "disabled"}}
    return {}


def non_thinking_provider_options(model: str) -> dict:
    """Use LangExtract's supported SDK field to disable DeepSeek thinking."""
    return {"reasoning_effort": "none"} if non_thinking_options(model) else {}


# ═══════════════════════════════════════════════════════════════════════════════
# Entity / Intent / Relation Enums
# ═══════════════════════════════════════════════════════════════════════════════

class EntityType(str, Enum):
    """Enterprise entity types — 10 classes per blueprint §2.4.3."""
    PROJECT_METADATA = "project_metadata"
    PERSON_ROLE = "person_role"
    PROCESS_STEP = "process_step"
    METRIC = "metric"
    MILESTONE = "milestone"
    DELIVERABLE = "deliverable"
    RISK_ITEM = "risk_item"
    REGULATION_REF = "regulation_ref"
    DEPARTMENT = "department"
    TIMELINE_EVENT = "timeline_event"


class QueryIntent(str, Enum):
    """Enterprise query intent types — 4 classes per blueprint §2.4.1."""
    POLICY_LOOKUP = "policy_lookup"
    PROCESS_ATTRIBUTION = "process_attribution"
    METRIC = "metric"
    HYBRID = "hybrid"


class RelationType(str, Enum):
    """KG edge relation types — 10 types per blueprint §2.4.3."""
    CO_OCCURS_WITH = "co_occurs_with"
    SAME_TYPE = "same_type"
    ADJACENT_TO = "adjacent_to"
    REPORTS_TO = "reports_to"
    OWNED_BY = "owned_by"
    REFERENCES = "references"
    HAS_MILESTONE = "has_milestone"
    PRODUCES = "produces"
    MITIGATES = "mitigates"
    HAS_METRIC = "has_metric"


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MAX_TOTAL_CANDIDATES = 5
DEFAULT_MAX_CONTEXT_TOKENS = 4000
DEFAULT_ENABLE_CROSS_ENCODER = True
DEFAULT_ENABLE_MULTI_QUERY = False
DEFAULT_ENABLE_GLOBAL_MODE = False
DEFAULT_PER_SOURCE_CAPS: dict[str, int] = {
    "vector": 2,
    "kg": 2,
    "bm25": 1,
    "table": 1,
    "multi_query": 1,
}


def default_per_source_caps() -> dict[str, int]:
    """Return a copy of the default per-source retrieval caps."""
    return DEFAULT_PER_SOURCE_CAPS.copy()


@dataclass
class RetrievalConfig:
    """Retrieval pipeline configuration."""
    max_total_candidates: int = DEFAULT_MAX_TOTAL_CANDIDATES
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    enable_cross_encoder: bool = DEFAULT_ENABLE_CROSS_ENCODER  # Cross-encoder rerank after RRF
    enable_multi_query: bool = DEFAULT_ENABLE_MULTI_QUERY
    enable_global_mode: bool = DEFAULT_ENABLE_GLOBAL_MODE
    vector_top_k: int = DEFAULT_PER_SOURCE_CAPS["vector"]
    table_top_k: int = DEFAULT_PER_SOURCE_CAPS["table"]
    kg_top_k: int = DEFAULT_PER_SOURCE_CAPS["kg"]
    bm25_top_k: int = DEFAULT_PER_SOURCE_CAPS["bm25"]
    multi_query_top_k: int = DEFAULT_PER_SOURCE_CAPS["multi_query"]
    rrf_k: int = 60
    rerank_budget_ms: int = 500
    rerank_max_candidates: int = 4
    rerank_high_recall_max_candidates: int = 6
    rerank_max_chars: int = 4096
    rerank_score_threshold: float = -2.0
    min_rerank_keep: int = 2
    per_source_caps: dict[str, int] = field(default_factory=default_per_source_caps)
    enabled_sources: tuple[str, ...] | None = None
    include_evidence_trace: bool = False

    def __post_init__(self):
        self.enabled_sources = normalize_enabled_sources(self.enabled_sources)


@dataclass
class EmbeddingConfig:
    """Embedding module configuration."""
    model_name: str = "BAAI/bge-small-zh-v1.5"
    dimension: int = 512
    batch_size: int = 32


@dataclass
class GenerationConfig:
    """LLM generation configuration."""
    model: str = field(default_factory=lambda: os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-flash"))
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout: int = 120


@dataclass
class ChunkConfig:
    """Document chunking configuration."""
    strategy: int = 2  # 1=fixed, 2=semantic, 3=entity-aware
    chunk_size_tokens: int = 512
    overlap_tokens: int = 64
    dedup: bool = True
    dedup_threshold: float = 0.85


# ═══════════════════════════════════════════════════════════════════════════════
# Entity type display metadata (for frontend)
# ═══════════════════════════════════════════════════════════════════════════════

ENTITY_TYPE_LABELS: dict[str, str] = {
    "project_metadata": "项目信息",
    "person_role": "人员角色",
    "process_step": "流程步骤",
    "metric": "指标数据",
    "milestone": "里程碑",
    "deliverable": "交付物",
    "risk_item": "风险项",
    "regulation_ref": "制度引用",
    "department": "部门",
    "timeline_event": "时间节点",
}

ENTITY_TYPE_COLORS: dict[str, str] = {
    "project_metadata": "#3b82f6",
    "person_role": "#22c55e",
    "process_step": "#a855f7",
    "metric": "#eab308",
    "milestone": "#f97316",
    "deliverable": "#ec4899",
    "risk_item": "#ef4444",
    "regulation_ref": "#8b5cf6",
    "department": "#14b8a6",
    "timeline_event": "#06b6d4",
}

RELATION_LABELS: dict[str, str] = {
    "co_occurs_with": "共现",
    "same_type": "同类",
    "adjacent_to": "相邻",
    "reports_to": "汇报给",
    "owned_by": "归属",
    "references": "引用",
    "has_milestone": "里程碑",
    "produces": "产出",
    "mitigates": "缓解",
    "has_metric": "指标",
}

# Legacy academic types (for backward compatibility with existing KG data)
LEGACY_ENTITY_TYPES = {
    "paper_metadata", "section_header", "model_component",
    "dataset", "method", "definition", "equation", "reference", "claim",
    "task", "table", "figure", "equation_parameter",
}
