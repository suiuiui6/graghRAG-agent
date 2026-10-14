"""Local dictionary contracts using durable YAML and real matching algorithms."""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import domain_dict
from domain_dict import DomainDict, DomainTerm, _edit_distance


@pytest.fixture
def dictionary(tmp_path):
    path = tmp_path / "terms.yaml"
    path.write_text(yaml.safe_dump([
        {"term": "作业安全分析", "synonyms": ["任务风险分析"], "abbreviations": ["JSA", "Job Safety Analysis"],
         "related": ["危险辨识", "风险评估"], "entity_type": "process_step", "category": "safety", "description": "作业前风险控制"},
        {"term": "动火", "synonyms": ["热作业"], "abbreviations": ["HW"], "category": "permit"},
        {"term": "隔离", "category": "permit"},
    ], allow_unicode=True), encoding="utf-8")
    result = DomainDict(path)
    assert result.loaded is False
    assert result.load() == 3
    return result


def test_load_categories_and_serializable_entry_defaults(dictionary):
    assert dictionary.loaded is True
    assert dictionary.stats() == {"total_terms": 3, "synonym_index_size": 4, "by_category": {"safety": 1, "permit": 2}}
    assert {item["term"] for item in dictionary.list_terms("permit")} == {"动火", "隔离"}
    assert dictionary.list_terms("unknown") == []
    assert dictionary.get("absent") is None
    assert DomainTerm({"term": "默认"}).to_dict() == {"term": "默认", "synonyms": [], "abbreviations": [],
            "related": [], "entity_type": None, "category": "general", "description": ""}


@pytest.mark.parametrize("content", [None, "", "{}", "42"])
def test_missing_or_nonlist_yaml_loads_as_empty_dictionary(tmp_path, content):
    path = tmp_path / "dictionary.yaml"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    dictionary = DomainDict(path)
    assert dictionary.load() == 0 and dictionary.loaded
    assert dictionary.expand_query("unknown") == "unknown"
    assert dictionary.resolve_abbreviations("JSA") == "JSA"
    assert dictionary.get_related_hints("unknown") == ""


def test_reload_replaces_stale_terms_from_durable_yaml(dictionary):
    dictionary._path.write_text("- term: 新术语\n  synonyms: [新简称]\n  category: custom\n", encoding="utf-8")
    assert dictionary.reload() == 1
    assert dictionary.get("动火") is None
    assert dictionary.resolve_abbreviations("JSA") == "JSA"
    assert dictionary.resolve_abbreviations("新简称") == "新术语"
    fresh = DomainDict(dictionary._path)
    assert fresh.load() == 1 and fresh.list_terms() == dictionary.list_terms()


def test_malformed_yaml_does_not_silently_claim_success(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- term: [unterminated", encoding="utf-8")
    dictionary = DomainDict(path)
    with pytest.raises(yaml.YAMLError):
        dictionary.load()
    assert dictionary.loaded is False


def test_crud_updates_reverse_indexes_without_renaming_canonical(dictionary):
    assert dictionary.add({"term": "许可", "synonyms": ["票证"], "abbreviations": ["PTW", "Long permit name"]})
    assert not dictionary.add({"term": "许可", "synonyms": ["坏别名"]})
    assert dictionary.resolve_abbreviations("PTW 票证") == "许可 许可"
    assert dictionary.resolve_abbreviations("Long permit name") == "Long permit name"
    assert dictionary.update("许可", {"term": "不准改名", "synonyms": ["工作票"], "abbreviations": ["WP"], "category": "permit"})
    assert dictionary.get("许可")["category"] == "permit"
    assert dictionary.get("不准改名") is None
    assert dictionary.resolve_abbreviations("PTW 票证 WP 工作票") == "PTW 票证 许可 许可"
    assert not dictionary.update("unknown", {"term": "x"})
    assert dictionary.delete("许可") and not dictionary.delete("许可")
    assert dictionary.resolve_abbreviations("WP 工作票") == "WP 工作票"
    assert dictionary.stats()["total_terms"] == 3


@pytest.mark.parametrize("query,expected", [
    ("JSA", "JSA 任务风险分析 作业安全分析"),
    ("作业安全分析", "作业安全分析 任务风险分析"),
    ("任务风险分析", "任务风险分析 作业安全分析"),
    ("JSA 作业安全分析 任务风险分析", "JSA 作业安全分析 任务风险分析"),
    ("隔离", "隔离"), ("unknown", "unknown"),
])
def test_exact_query_expansion_is_deterministic_and_deduplicated(dictionary, query, expected):
    assert dictionary.expand_query(query) == expected


def test_fuzzy_expansion_corrects_short_english_typo_but_respects_threshold(dictionary):
    assert dictionary.expand_query("JSB", fuzzy_threshold=.6) == "JSB 任务风险分析 作业安全分析"
    assert dictionary.expand_query("JSB", fuzzy_threshold=.9) == "JSB"


@pytest.mark.parametrize("left,right,distance", [("", "abc", 3), ("a", "", 1), ("kitten", "sitting", 3), ("作业", "作业", 0)])
def test_edit_distance_counts_insertions_substitutions_and_deletions(left, right, distance):
    assert _edit_distance(left, right) == distance


@pytest.mark.parametrize("left,right,expected", [("JSA", "jsa", 1), ("JSB", "JSA", 2/3),
    ("安全作业", "安全工作", 3/4), ("", "中文", 0), ("", "", 1)])
def test_similarity_normalizes_ascii_and_uses_character_overlap(left, right, expected):
    assert DomainDict._fuzzy_similarity(left, right) == pytest.approx(expected)


def test_related_hints_enforce_prompt_size_limits(dictionary):
    for index in range(4):
        dictionary.add({"term": f"规则{index}", "related": [f"相关{i}" for i in range(8)], "description": "详" * 80})
    hints = dictionary.get_related_hints("规则0 规则1 规则2 规则3")
    assert hints.startswith("领域知识提示:")
    assert hints.count("相关概念包括") == 3
    assert "规则3" not in hints and "相关5" not in hints
    assert "详" * 60 in hints and "详" * 61 not in hints
    assert dictionary.get_related_hints("absent") == ""


@pytest.mark.parametrize("keyword,expected", [("作业安全", {"作业安全分析"}), ("任务", {"作业安全分析"}),
    ("风险控制", {"作业安全分析"}), ("absent", set())])
def test_search_covers_canonical_synonym_description_and_no_match(dictionary, keyword, expected):
    assert {row["term"] for row in dictionary.search(keyword)} == expected


def test_search_abbreviations_is_case_insensitive(dictionary):
    assert {row["term"] for row in dictionary.search("jsa")} == {"作业安全分析"}
    assert dictionary.search("JSA") == dictionary.search("jsa")


@pytest.mark.parametrize("field", ["term", "synonyms", "abbreviations", "description"])
def test_ascii_search_normalizes_all_searchable_fields(dictionary, field):
    value = ["MixedCase"] if field in ("synonyms", "abbreviations") else "MixedCase"
    data = {"term": "新条目", field: value}
    assert dictionary.add(data)
    assert {row["term"] for row in dictionary.search("MIXEDCASE")} == {data["term"]}


def test_singleton_loads_local_configuration_once(monkeypatch, dictionary):
    monkeypatch.setattr(domain_dict, "_dict_instance", None)
    monkeypatch.setattr(domain_dict, "DEFAULT_DICT_PATH", dictionary._path)
    first = domain_dict.get_domain_dict()
    assert first.loaded and len(first.list_terms()) == 3
    assert domain_dict.get_domain_dict() is first
