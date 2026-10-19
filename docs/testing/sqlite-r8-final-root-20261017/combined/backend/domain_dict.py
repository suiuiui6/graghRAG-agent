"""
Domain Dictionary — §10.1 of enterprise-evolution-blueprint.

Loads HSE domain terms from YAML, builds in-memory index, provides
3-layer query expansion for retrieval pipeline integration:
  Layer 1: Synonym expansion → multi-query recall
  Layer 2: Abbreviation expansion → standard term substitution
  Layer 3: Related term hints → prompt augmentation
"""

from __future__ import annotations

from pathlib import Path

import yaml

from logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DICT_PATH = Path(__file__).parent / "config" / "domain_dict.yaml"


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            ))
        prev = curr
    return prev[-1]


class DomainTerm:
    """A single domain dictionary entry."""

    __slots__ = ("term", "synonyms", "abbreviations", "related",
                 "entity_type", "category", "description")

    def __init__(self, data: dict):
        self.term: str = data.get("term", "")
        self.synonyms: list[str] = data.get("synonyms", [])
        self.abbreviations: list[str] = data.get("abbreviations", [])
        self.related: list[str] = data.get("related", [])
        self.entity_type: str | None = data.get("entity_type")
        self.category: str = data.get("category", "general")
        self.description: str = data.get("description", "")

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "synonyms": self.synonyms,
            "abbreviations": self.abbreviations,
            "related": self.related,
            "entity_type": self.entity_type,
            "category": self.category,
            "description": self.description,
        }


class DomainDict:
    """In-memory domain dictionary with fast lookup for query processing."""

    def __init__(self, dict_path: Path | None = None):
        self._path = Path(dict_path) if dict_path else DEFAULT_DICT_PATH
        self._terms: dict[str, DomainTerm] = {}
        self._synonym_index: dict[str, str] = {}    # synonym/abbr → canonical term
        self._category_index: dict[str, list[str]] = {}
        self._loaded = False

    # ── load / reload ─────────────────────────────────────────────────

    def load(self) -> int:
        """Load terms from YAML file. Returns count of loaded terms."""
        self._terms.clear()
        self._synonym_index.clear()
        self._category_index.clear()

        if not self._path.exists():
            logger.warning("domain_dict_not_found", path=str(self._path))
            self._loaded = True
            return 0

        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning("domain_dict_invalid_format")
            self._loaded = True
            return 0

        for entry in raw:
            term = DomainTerm(entry)
            self._terms[term.term] = term
            # Build reverse index
            for syn in term.synonyms:
                self._synonym_index[syn] = term.term
            for abbr in term.abbreviations:
                # Skip English-only long forms as index keys
                if len(abbr) <= 10:
                    self._synonym_index[abbr] = term.term
            # Category index
            cat = term.category
            if cat not in self._category_index:
                self._category_index[cat] = []
            self._category_index[cat].append(term.term)

        self._loaded = True
        logger.info("domain_dict_loaded", terms=len(self._terms),
                     synonyms=len(self._synonym_index))
        return len(self._terms)

    def reload(self) -> int:
        return self.load()

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ── query expansion (3-layer) ─────────────────────────────────────

    @staticmethod
    def _fuzzy_similarity(a: str, b: str) -> float:
        """Compute simple fuzzy similarity between two strings.

        Handles short English tokens with edit distance and longer Chinese
        segments with character overlap ratio.
        """
        a_lower = a.lower()
        b_lower = b.lower()

        # Identical → 1.0
        if a_lower == b_lower:
            return 1.0

        # Short English (< 20 chars combined): edit-distance ratio
        if len(a_lower) < 20 and len(b_lower) < 20 and a_lower.isascii() and b_lower.isascii():
            max_len = max(len(a_lower), len(b_lower))
            if max_len == 0:
                return 0.0
            # Simple Levenshtein-like ratio
            edits = _edit_distance(a_lower, b_lower)
            return 1.0 - edits / max_len

        # Chinese / mixed: character overlap
        a_chars = set(a)
        b_chars = set(b)
        if not a_chars or not b_chars:
            return 0.0
        overlap = len(a_chars & b_chars)
        return overlap / max(len(a_chars), len(b_chars))

    def expand_query(self, query: str, fuzzy_threshold: float = 0.7) -> str:
        """Layer 1+2: Expand query with synonyms and resolve abbreviations.

        Supports exact substring matches AND fuzzy matching for near-miss
        terms (typos, partial abbreviations, alternative spellings).

        Returns an enriched query string for multi-path retrieval.
        """
        if not self._terms:
            return query

        matched_terms: list[tuple[str, DomainTerm, str, bool]] = []
        matched_term_names: set[str] = set()
        for term_name, term_obj in self._terms.items():
            candidates = [term_name] + term_obj.synonyms + term_obj.abbreviations
            best_match: tuple[str, bool] | None = None
            for candidate in candidates:
                # Exact match first
                if candidate in query:
                    best_match = (candidate, True)
                    break
                # Fuzzy: check if candidate has significant overlap with any query token
                if not best_match:
                    sim = self._fuzzy_similarity(candidate, query)
                    if sim >= fuzzy_threshold:
                        best_match = (candidate, False)
            if best_match is not None:
                matched_terms.append((term_name, term_obj, best_match[0], best_match[1]))
                matched_term_names.add(term_name)

        if not matched_term_names:
            return query

        expansions: set[str] = set()
        for term_name, term_obj, matched_candidate, exact in matched_terms:
            expansions.update(term_obj.synonyms)
            if matched_candidate != term_name:
                expansions.add(term_name)
            # For fuzzy matches, also add the canonical term for disambiguation
            if not exact:
                expansions.add(term_name)

        if not expansions:
            return query

        # Dedup against already-present terms in the query
        new_terms = sorted(expansions - set(query.split()))
        if not new_terms:
            return query

        expanded = query + " " + " ".join(new_terms)
        logger.debug("domain_dict_expanded", original=query,
                     added_terms=new_terms)
        return expanded

    def resolve_abbreviations(self, query: str) -> str:
        """Layer 2: Replace abbreviations with canonical terms."""
        if not self._synonym_index:
            return query
        result = query
        for abbr, canonical in self._synonym_index.items():
            if abbr in result and abbr != canonical:
                result = result.replace(abbr, canonical)
        return result

    def get_related_hints(self, query: str) -> str:
        """Layer 3: Find related terms for prompt augmentation.

        Returns a string like '注意: 动火作业的相关概念包括: ...'
        """
        if not self._terms:
            return ""

        matched_terms: list[DomainTerm] = []
        for term_obj in self._terms.values():
            candidates = [term_obj.term] + term_obj.synonyms + term_obj.abbreviations
            if any(c in query for c in candidates):
                matched_terms.append(term_obj)

        if not matched_terms:
            return ""

        lines = ["领域知识提示:"]
        for t in matched_terms[:3]:  # max 3 matched terms
            related_str = "、".join(t.related[:5])  # max 5 related
            lines.append(f"- {t.term} ({t.description[:60]}): 相关概念包括 {related_str}")

        return "\n".join(lines)

    # ── CRUD ──────────────────────────────────────────────────────────

    def list_terms(self, category: str | None = None) -> list[dict]:
        """List all terms, optionally filtered by category."""
        result = []
        for t in self._terms.values():
            if category and t.category != category:
                continue
            result.append(t.to_dict())
        return result

    def search(self, keyword: str) -> list[dict]:
        """Search terms by keyword (matches term name + synonyms + abbreviations)."""
        kw = keyword.lower()
        result = []
        for t in self._terms.values():
            if kw in t.term.lower() or any(kw in s.lower() for s in t.synonyms) or any(kw in a.lower() for a in t.abbreviations):
                result.append(t.to_dict())
            elif kw in t.description.lower():
                result.append(t.to_dict())
        return result

    def get(self, term: str) -> dict | None:
        t = self._terms.get(term)
        return t.to_dict() if t else None

    def add(self, data: dict) -> bool:
        term = DomainTerm(data)
        if term.term in self._terms:
            logger.warning("domain_dict_duplicate", term=term.term)
            return False
        self._terms[term.term] = term
        for syn in term.synonyms:
            self._synonym_index[syn] = term.term
        for abbr in term.abbreviations:
            if len(abbr) <= 10:
                self._synonym_index[abbr] = term.term
        return True

    def update(self, term_name: str, data: dict) -> bool:
        if term_name not in self._terms:
            return False
        # Remove old index entries
        old = self._terms[term_name]
        for syn in old.synonyms:
            self._synonym_index.pop(syn, None)
        for abbr in old.abbreviations:
            self._synonym_index.pop(abbr, None)
        # Update
        new_term = DomainTerm({**old.to_dict(), **data, "term": term_name})
        self._terms[term_name] = new_term
        for syn in new_term.synonyms:
            self._synonym_index[syn] = term_name
        for abbr in new_term.abbreviations:
            if len(abbr) <= 10:
                self._synonym_index[abbr] = term_name
        return True

    def delete(self, term_name: str) -> bool:
        if term_name not in self._terms:
            return False
        old = self._terms.pop(term_name)
        for syn in old.synonyms:
            self._synonym_index.pop(syn, None)
        for abbr in old.abbreviations:
            self._synonym_index.pop(abbr, None)
        return True

    def stats(self) -> dict:
        cats = {}
        for t in self._terms.values():
            cats[t.category] = cats.get(t.category, 0) + 1
        return {
            "total_terms": len(self._terms),
            "synonym_index_size": len(self._synonym_index),
            "by_category": cats,
        }


# ── global singleton ───────────────────────────────────────────────────

_dict_instance: DomainDict | None = None


def get_domain_dict() -> DomainDict:
    global _dict_instance
    if _dict_instance is None:
        _dict_instance = DomainDict()
        _dict_instance.load()
    return _dict_instance
