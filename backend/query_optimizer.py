"""
Advanced Query Optimization — §3.1 of rag-engineering-blueprint-v1.0.

Extends the basic Query Preprocessing (§2.4.1) with:
  1. Multi-turn conversation management — pronoun resolution across turns
  2. User profile adaptation — adjust answer granularity by role
  3. Domain dictionary injection — terminology expansion for better recall
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DomainDictionary:
    """Terminology mapping for cross-language / synonym expansion."""
    entries: dict[str, list[str]] = field(default_factory=dict)

    def expand(self, query: str) -> list[str]:
        """Return additional search terms for a query."""
        extra: list[str] = []
        query_lower = query.lower()
        for term, synonyms in self.entries.items():
            if term.lower() in query_lower:
                for s in synonyms:
                    if s.lower() not in query_lower:
                        extra.append(s)
        return extra


@dataclass
class UserProfile:
    """User background and preference for answer adaptation."""
    role: str = "general"  # "executive" | "analyst" | "engineer" | "general"
    detail_level: str = "standard"  # "concise" | "standard" | "detailed"
    preferred_language: str = "auto"  # "zh" | "en" | "auto"


# ═══════════════════════════════════════════════════════════════════════════════
# Default Enterprise Domain Dictionary
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_ENTERPRISE_DICT: dict[str, list[str]] = {
    # 项目管理
    "变更": ["变更管理", "变更流程", "变更申请", "CM"],
    "预算": ["预算管理", "预算执行", "成本控制", "费用"],
    "里程碑": ["关键节点", "阶段性目标", "checkpoint", "节点"],
    "验收": ["终验", "验收评审", "交付验收", "acceptance"],
    # 人员角色
    "项目经理": ["PM", "项目负责人", "project manager"],
    "审批人": ["审批者", "签批人", "approver", "审核人"],
    "负责人": ["责任人", "owner", "主管", "牵头人"],
    # 流程管理
    "审批": ["签批", "核准", "批准", "approval"],
    "流程": ["工作流", "workflow", "process", "步骤"],
    "制度": ["管理办法", "规范", "标准", "policy", "regulation", "SOP"],
    # 风险质量
    "风险": ["隐患", "risk", "不确定性", "问题"],
    "质量": ["quality", "QA", "合格", "达标"],
    "合规": ["compliance", "符合性", "遵从"],
    # 数据指标
    "执行率": ["完成率", "达成率", "completion rate"],
    "进度": ["进展", "完成百分比", "progress"],
    "KPI": ["关键绩效", "指标", "考核指标"],
    # 技术
    "数字化": ["digital transformation", "信息化", "智能化"],
    "系统": ["平台", "system", "应用"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Profile-specific Prompt Modifiers
# ═══════════════════════════════════════════════════════════════════════════════

PROFILE_MODIFIERS: dict[str, str] = {
    "executive": (
        "请提供高层摘要，聚焦关键结论和决策所需的核心数据。"
        "使用要点列表，每条不超过两行。"
    ),
    "analyst": (
        "请提供详细分析，包含具体数据、趋势对比和统计指标。"
        "优先使用 Markdown 表格展示数值。"
    ),
    "engineer": (
        "请提供技术细节，包含具体参数、流程步骤和实施要点。"
        "引用相关制度和规范文件。"
    ),
    "general": "",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Query Optimizer
# ═══════════════════════════════════════════════════════════════════════════════

class QueryOptimizer:
    """Advanced query optimization — extends basic preprocessing with §3.1 features.

    Usage:
        optimizer = QueryOptimizer()
        optimized = optimizer.optimize(
            raw_query="它的预算花了多少",
            chat_history=[{"role": "user", "content": "XX项目进展如何"}],
            profile=UserProfile(role="executive"),
        )
        # → optimized query with pronouns resolved, domain terms injected, profile hints
    """

    def __init__(
        self,
        domain_dict: dict[str, list[str]] | None = None,
        profile_modifiers: dict[str, str] | None = None,
        max_history_turns: int = 6,
    ):
        self.domain_dict = DomainDictionary(domain_dict or DEFAULT_ENTERPRISE_DICT)
        self.profile_modifiers = profile_modifiers or PROFILE_MODIFIERS
        self.max_history_turns = max_history_turns

    def optimize(
        self,
        raw_query: str,
        chat_history: list[dict] | None = None,
        profile: UserProfile | None = None,
    ) -> OptimizedQuery:
        """Run all three optimization steps on the raw query.

        Args:
            raw_query: User's raw question.
            chat_history: Previous conversation turns.
            profile: User profile for answer adaptation.

        Returns:
            OptimizedQuery with enhanced query and metadata.
        """
        result = OptimizedQuery(raw_query=raw_query)

        # Step 1: Multi-turn pronoun resolution
        result.resolved_query = _resolve_pronouns(
            raw_query, chat_history, self.max_history_turns
        )

        # Step 2: Domain dictionary injection
        extra_terms = self.domain_dict.expand(result.resolved_query)
        result.expanded_terms = extra_terms

        # Build enhanced search query: resolved query + domain terms
        if extra_terms:
            result.enhanced_query = (
                f"{result.resolved_query} {' '.join(extra_terms[:5])}"
            )
        else:
            result.enhanced_query = result.resolved_query

        # Step 3: User profile adaptation
        if profile:
            result.profile_hint = _build_profile_hint(profile, self.profile_modifiers)
            result.profile = profile

        return result


@dataclass
class OptimizedQuery:
    """Output of QueryOptimizer.optimize()."""
    raw_query: str
    resolved_query: str = ""
    enhanced_query: str = ""
    expanded_terms: list[str] = field(default_factory=list)
    profile_hint: str = ""
    profile: UserProfile | None = None

    def __post_init__(self):
        if not self.resolved_query:
            self.resolved_query = self.raw_query
        if not self.enhanced_query:
            self.enhanced_query = self.resolved_query


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Multi-turn Pronoun Resolution
# ═══════════════════════════════════════════════════════════════════════════════

# Chinese pronoun patterns and their likely referents
PRONOUN_PATTERNS: dict[str, str] = {
    "它": "前述主体",
    "它们": "前述多个主体",
    "其": "前述主体",
    "该": "前述",
    "这个": "前述",
    "那个": "前述",
    "这些": "前述多个",
    "那些": "前述多个",
    "前者": "前述第一个",
    "后者": "前述第二个",
}

# Entity patterns to extract from history for reference resolution
ENTITY_PATTERN = re.compile(
    r'(?:项目|工程|系统|平台|方案)[一-鿿]{0,10}(?:项目|工程|系统|平台|方案)?'
)


def _resolve_pronouns(
    raw_query: str,
    chat_history: list[dict] | None,
    max_turns: int = 6,
) -> str:
    """Resolve pronouns in the query using conversation history.

    Strategy:
    1. If no pronouns detected → return raw query unchanged
    2. Extract key entities from recent history
    3. If LLM API is available → use LLM for precise resolution
    4. Fallback: simple heuristic replacement based on entity extraction
    """
    if not chat_history:
        return raw_query

    # Check if query contains pronouns that need resolution
    has_pronouns = any(p in raw_query for p in PRONOUN_PATTERNS)
    if not has_pronouns:
        return raw_query

    # Try LLM-based resolution
    resolved = _llm_resolve_pronouns(raw_query, chat_history, max_turns)
    if resolved and resolved != raw_query:
        return resolved

    # Fallback: heuristic resolution
    return _heuristic_resolve_pronouns(raw_query, chat_history, max_turns)


def _llm_resolve_pronouns(
    query: str, history: list[dict], max_turns: int,
) -> str | None:
    """Use LLM to resolve pronouns precisely."""
    try:
        import requests

        recent = _recent_history(history, max_turns)
        history_text = "\n".join(
            f"{m['role']}: {m['content'][:300]}" for m in recent
        )

        prompt = (
            "Resolve pronouns in the user's latest query using conversation context.\n"
            "Output ONLY the resolved query, no explanation.\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Latest query: {query}\n\n"
            "Resolved query:"
        )

        api_key = os.getenv("LANGEXTRACT_API_KEY", "")
        base_url = os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com")

        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 150,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001  # LLM 查询改写为可选增强，调用失败即返回 None 回退原查询
        return None


def _heuristic_resolve_pronouns(
    query: str, history: list[dict], max_turns: int,
) -> str:
    """Fallback: extract entities from history and substitute pronouns."""
    recent = _recent_history(history, max_turns)
    history_text = " ".join(
        m.get("content", "") for m in recent if m.get("role") == "user"
    )

    # Extract project names, system names, etc. from history
    entities = ENTITY_PATTERN.findall(history_text)
    if not entities:
        return query

    # Use the most recently mentioned entity
    referent = entities[-1]

    result = query
    for pronoun, _meaning in PRONOUN_PATTERNS.items():
        if pronoun in result:
            result = result.replace(pronoun, referent, 1)

    return result


def _recent_history(history: list[dict], max_turns: int) -> list[dict]:
    """Return the most recent N turns of conversation."""
    if len(history) <= max_turns:
        return history
    return history[-max_turns:]


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: User Profile Adaptation
# ═══════════════════════════════════════════════════════════════════════════════

def _build_profile_hint(profile: UserProfile, modifiers: dict[str, str]) -> str:
    """Build a profile-specific instruction for the LLM."""
    hint = modifiers.get(profile.role, "")

    # Language preference
    if profile.preferred_language == "zh":
        hint += " 请用中文回答。"
    elif profile.preferred_language == "en":
        hint += " Please answer in English."

    # Detail level
    if profile.detail_level == "concise":
        hint += " 答案请保持简洁，控制在200字以内。"
    elif profile.detail_level == "detailed":
        hint += " 请提供详尽回答，包含所有相关细节和引用来源。"

    return hint.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration helper — merges optimizer output into existing retrieval pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def build_enhanced_system_prompt(
    base_system_prompt: str,
    optimized: OptimizedQuery,
) -> str:
    """Enhance the system prompt with optimizer outputs.

    Injects profile hints and domain context into the existing system prompt.
    """
    parts = [base_system_prompt]

    if optimized.profile_hint:
        parts.append(f"\n[USER CONTEXT]\n{optimized.profile_hint}")

    if optimized.expanded_terms:
        parts.append(
            f"\n[DOMAIN TERMS]\n"
            f"以下相关术语可辅助理解查询意图: {', '.join(optimized.expanded_terms[:10])}"
        )

    return "\n".join(parts)
