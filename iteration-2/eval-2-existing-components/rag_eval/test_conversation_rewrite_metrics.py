from __future__ import annotations

import importlib.util
import json
import unittest
import uuid
from pathlib import Path


METRICS_PATH = Path(__file__).with_name("conversation_rewrite_metrics.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("conversation_rewrite_metrics", METRICS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {METRICS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConversationRewriteMetricsTests(unittest.TestCase):
    def test_per_question_marks_followup_with_rewrite_as_success(self):
        module = _load_module()
        question = {
            "qid": "MT01",
            "category": "MT",
            "question": "它对应的弃电量是多少？",
            "session_id": "mt-session",
            "conversation_setup": [{"question": "W4S1 是什么？"}],
            "expected_keywords": ["W4S1", "弃电"],
        }
        run = {
            "qid": "MT01",
            "session_id": "mt-session",
            "rewritten_query": "在W4S1场景下对应的弃电量是多少？",
            "rewrite_reason": "coreference_resolution",
            "final_answer": "在W4S1场景下，对应的弃电量为173.7 MWh/日。",
        }

        row = module.per_question_metrics(question, run)

        self.assertTrue(row["is_followup"])
        self.assertEqual(row["rewrite_success"], 1)
        self.assertEqual(row["session_id_match"], 1)
        self.assertEqual(row["keyword_coverage"], 1.0)

    def test_per_question_does_not_require_rewrite_for_non_followup(self):
        module = _load_module()
        question = {
            "qid": "Q01",
            "category": "T1",
            "question": "这篇论文的标题是什么？",
            "expected_keywords": ["绿电直连"],
        }
        run = {
            "qid": "Q01",
            "session_id": "single-turn",
            "rewritten_query": None,
            "rewrite_reason": None,
            "final_answer": "这篇论文标题包含绿电直连。",
        }

        row = module.per_question_metrics(question, run)

        self.assertFalse(row["is_followup"])
        self.assertIsNone(row["rewrite_success"])
        self.assertEqual(row["keyword_coverage"], 1.0)

    def test_per_question_marks_alias_missing_from_sources_as_corpus_drift(self):
        module = _load_module()
        question = {
            "qid": "MT02",
            "category": "MT",
            "question": "它的绿电消纳率是多少？",
            "session_id": "mt-session-w2s2",
            "conversation_setup": [{"question": "论文中提到的 W2S2 场景是什么？"}],
            "expected_node_ids": ["n0036"],
            "expected_keywords": ["W2S2", "绿电"],
            "gold_aliases": ["W2S2"],
        }
        run = {
            "qid": "MT02",
            "session_id": "mt-session-w2s2",
            "rewritten_query": "在 W2S2 场景下，它的绿电消纳率是多少？",
            "rewrite_reason": "coreference_resolution",
            "final_answer": "根据当前检索到的证据，绿电指标从39.2%跃升至69.2%。",
            "retrieved_node_ids": ["n0099"],
            "source_labels": ["绿电指标"],
            "source_text_snippets": ["绿电指标是最大受益者，全满足率从39.2%跃升至69.2%。"],
        }

        row = module.per_question_metrics(question, run)

        self.assertEqual(row["gold_aliases"], ["W2S2"])
        self.assertEqual(row["gold_alias_found_in_rewrite"], ["W2S2"])
        self.assertEqual(row["gold_alias_found_in_sources"], [])
        self.assertEqual(row["eval_case_status"], "corpus_drift")
        self.assertEqual(row["eval_case_reason"], "alias_missing_by_string_match")

    def test_aggregate_reports_followup_support_and_success_rate(self):
        module = _load_module()
        rows = [
            {"rewrite_success": 1, "session_id_match": 1, "keyword_coverage": 1.0, "is_followup": True},
            {"rewrite_success": 0, "session_id_match": 1, "keyword_coverage": 0.5, "is_followup": True},
            {"rewrite_success": None, "session_id_match": 1, "keyword_coverage": 1.0, "is_followup": False},
        ]

        agg = module.aggregate(rows)

        self.assertEqual(agg["n_questions"], 3)
        self.assertEqual(agg["followup_questions"], 2)
        self.assertEqual(agg["rewrite_success_rate_macro"], 0.5)
        self.assertEqual(agg["session_id_match_rate_macro"], 1.0)

    def test_parse_args_accepts_custom_paths(self):
        module = _load_module()

        args = module.parse_args(
            [
                "--gt-path",
                "custom_gt.json",
                "--runs-path",
                "custom_runs.jsonl",
                "--out-json",
                "custom_metrics.json",
                "--out-md",
                "custom_report.md",
            ]
        )

        self.assertEqual(args.gt_path, "custom_gt.json")
        self.assertEqual(args.runs_path, "custom_runs.jsonl")
        self.assertEqual(args.out_json, "custom_metrics.json")
        self.assertEqual(args.out_md, "custom_report.md")

    def test_build_metrics_payload_supports_multiple_followups(self):
        module = _load_module()
        gt = {
            "_meta": {"name": "multiturn"},
            "questions": [
                {
                    "qid": "MT01",
                    "category": "MT",
                    "question": "它对应的弃电量是多少？",
                    "session_id": "s1",
                    "conversation_setup": [{"question": "W4S1 是什么？"}],
                    "expected_keywords": ["W4S1", "弃电"],
                },
                {
                    "qid": "MT02",
                    "category": "MT",
                    "question": "它的绿电消纳率是多少？",
                    "session_id": "s2",
                    "conversation_setup": [{"question": "W2S2 是什么？"}],
                    "expected_keywords": ["W2S2", "绿电"],
                },
                {
                    "qid": "Q01",
                    "category": "T1",
                    "question": "论文标题是什么？",
                    "expected_keywords": ["绿电直连"],
                },
            ],
        }
        runs = [
            {
                "qid": "MT01",
                "session_id": "s1",
                "rewritten_query": "在W4S1场景下对应的弃电量是多少？",
                "rewrite_reason": "coreference_resolution",
                "final_answer": "在W4S1场景下，对应的弃电量为173.7 MWh/日。",
            },
            {
                "qid": "MT02",
                "session_id": "s2",
                "rewritten_query": "在W2S2场景下它的绿电消纳率是多少？",
                "rewrite_reason": "coreference_resolution",
                "final_answer": "在W2S2场景下，绿电消纳率为95%。",
            },
            {
                "qid": "Q01",
                "session_id": "single-turn",
                "rewritten_query": None,
                "rewrite_reason": None,
                "final_answer": "这篇论文标题包含绿电直连。",
            },
        ]

        payload = module.build_metrics_payload(
            gt=gt,
            runs=runs,
            ground_truth_path=Path("ground_truth_multiturn.json"),
            raw_runs_path=Path("raw_runs_multiturn.jsonl"),
            report_path=Path("conversation_rewrite_report.md"),
        )

        self.assertEqual(payload["global"]["n_questions"], 3)
        self.assertEqual(payload["global"]["followup_questions"], 2)
        self.assertEqual(payload["global"]["rewrite_success_rate_macro"], 1.0)
        self.assertEqual(payload["_meta"]["ground_truth_path"], "ground_truth_multiturn.json")
        self.assertEqual(payload["_meta"]["raw_runs_path"], "raw_runs_multiturn.jsonl")

    def test_build_metrics_payload_counts_corpus_drift_cases(self):
        module = _load_module()
        gt = {
            "questions": [
                {
                    "qid": "MT02",
                    "category": "MT",
                    "question": "它的绿电消纳率是多少？",
                    "session_id": "mt-session-w2s2",
                    "conversation_setup": [{"question": "论文中提到的 W2S2 场景是什么？"}],
                    "expected_node_ids": ["n0036"],
                    "expected_keywords": ["W2S2", "绿电"],
                    "gold_aliases": ["W2S2"],
                }
            ]
        }
        runs = [
            {
                "qid": "MT02",
                "session_id": "mt-session-w2s2",
                "rewritten_query": "在 W2S2 场景下，它的绿电消纳率是多少？",
                "rewrite_reason": "coreference_resolution",
                "final_answer": "根据当前检索到的证据，绿电指标从39.2%跃升至69.2%。",
                "retrieved_node_ids": ["n0099"],
                "source_labels": ["绿电指标"],
                "source_text_snippets": ["绿电指标是最大受益者，全满足率从39.2%跃升至69.2%。"],
            }
        ]

        payload = module.build_metrics_payload(
            gt=gt,
            runs=runs,
            ground_truth_path=Path("ground_truth_multiturn_smoke.json"),
            raw_runs_path=Path("raw_runs_multiturn_smoke.jsonl"),
            report_path=Path("conversation_rewrite_report.md"),
        )

        self.assertEqual(payload["global"]["corpus_drift_cases"], 1)
        self.assertEqual(payload["global"]["valid_questions_for_scoring"], 0)

    def test_main_writes_outputs_for_custom_paths(self):
        module = _load_module()
        temp_root = Path(__file__).with_name(f"_tmp_conversation_rewrite_metrics_{uuid.uuid4().hex}")
        temp_root.mkdir()
        gt_path = temp_root / "gt.json"
        runs_path = temp_root / "runs.jsonl"
        out_json = temp_root / "metrics.json"
        out_md = temp_root / "report.md"

        gt_path.write_text(
            json.dumps(
                {
                    "questions": [
                        {
                            "qid": "MT01",
                            "category": "MT",
                            "question": "它对应的弃电量是多少？",
                            "session_id": "s1",
                            "conversation_setup": [{"question": "W4S1 是什么？"}],
                            "expected_keywords": ["W4S1", "弃电"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runs_path.write_text(
            json.dumps(
                {
                    "qid": "MT01",
                    "session_id": "s1",
                    "rewritten_query": "在W4S1场景下对应的弃电量是多少？",
                    "rewrite_reason": "coreference_resolution",
                    "final_answer": "在W4S1场景下，对应的弃电量为173.7 MWh/日。",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        module.main(
            [
                "--gt-path",
                str(gt_path),
                "--runs-path",
                str(runs_path),
                "--out-json",
                str(out_json),
                "--out-md",
                str(out_md),
            ]
        )

        self.assertTrue(out_json.exists())
        self.assertTrue(out_md.exists())
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["global"]["followup_questions"], 1)
        self.assertIn("Conversation Rewrite Evaluation Report", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
