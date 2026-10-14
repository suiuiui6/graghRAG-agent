"""Read-only case audit; helper fixtures are not model experiments or accuracy scores."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "iteration-2/eval-2-existing-components/rag_eval"
SOURCE = ROOT / "backend/output/mineru/ingest_2/full.md"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_helpers(path, names):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    namespace = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def main():
    source = SOURCE.read_text(encoding="utf-8")
    abstract = source.split("## 摘 要", 1)[1].split("关键词", 1)[0]
    expected = ["3554", "5820", "7111", "3669", "5652"]
    assert all(v in abstract for v in expected) and "168" not in abstract
    figures = sorted(set(re.findall(r"图\s*([1-6])\s*—", source)))
    assert figures == list("123456")
    runs, cases = [], []
    for path in sorted(EVAL.glob("raw_runs*.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        runs.append({"file": path.name, "rows": len(rows), "sha256": digest(path)})
        for line, row in enumerate(rows, 1):
            if row.get("qid") not in ("Q15", "Q16"):
                continue
            answer = row.get("final_answer", "")
            cases.append({
                "file": path.name, "line": line, "qid": row["qid"],
                "timestamp": row.get("timestamp"), "query": row["query"],
                "generation_error": "生成回答时发生错误" in answer,
                "mentioned_figures": sorted(set(re.findall(r"图\s*([1-6])", answer))),
                "mentioned_abstract_cost_values": [v for v in expected if v in answer],
                "mentions_168": "168" in answer,
                "exhaustive_phrase_present": "文档中未提及除上述" in answer,
                "answer": answer,
            })
    q = "论文摘要中提到的吨氨成本类经济指标分别有哪些？"
    retrieval = ROOT / "backend/retrieval.py"
    generator = ROOT / "backend/generator.py"
    rh = load_helpers(retrieval, ["_is_summary_metric_query"])
    gh = load_helpers(generator, ["_extract_key_entities_from_chunks", "_supplement_key_entities"])
    diagnostic = {
        "Q16_summary_metric_trigger": rh["_is_summary_metric_query"](q),
        "summary_MWh_positive_control": rh["_is_summary_metric_query"]("摘要中网购电量是多少MWh？"),
        "no_summary_negative_control": rh["_is_summary_metric_query"]("网购电量是多少MWh？"),
    }
    assert diagnostic == {"Q16_summary_metric_trigger": False, "summary_MWh_positive_control": True, "no_summary_negative_control": False}
    appendix = source.split("## 附录 A：核心代码结构说明", 1)[1].split("## 附录 B", 1)[0]
    fixture_answer = "摘要列有3554、5820、7111、3669、5652元/吨。"
    diagnostic["controlled_appendix_fixture_output"] = gh["_supplement_key_entities"](
        fixture_answer, [{"text": appendix, "score": 1.0}], q)
    assert "补充数据：" in diagnostic["controlled_appendix_fixture_output"]
    content = next(SOURCE.parent.glob("*content_list.json"))
    result = {
        "audit_type": "historical_cases_and_current_pure_helpers_not_endpoint_replay",
        "source_sha256": digest(SOURCE), "content_json_sha256": digest(content),
        "ground_truth_sha256": digest(EVAL / "ground_truth.json"),
        "helper_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (retrieval, generator)},
        "source_figures": figures, "abstract_cost_values": expected,
        "old_KG_available": (ROOT / "backend/output/kg/doc_ingest_232e1611").exists(),
        "bundles": runs, "case_records": cases, "local_helper_diagnostics": diagnostic,
        "limits": ["regex presence is not semantic scoring", "repeated questions are not independent samples", "no historical corpus byte identity established", "no model call or current endpoint replay"],
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
