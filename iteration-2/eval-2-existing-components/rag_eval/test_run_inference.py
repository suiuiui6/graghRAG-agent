import importlib.util
import unittest
from pathlib import Path


RUN_INFERENCE_PATH = Path(__file__).with_name("run_inference.py")


def _load_run_inference_module():
    spec = importlib.util.spec_from_file_location("run_inference", RUN_INFERENCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {RUN_INFERENCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunInferenceTests(unittest.TestCase):
    def test_resolve_output_paths_prefers_cli_over_defaults(self):
        module = _load_run_inference_module()
        args = type(
            "Args",
            (),
            {
                "out_path": "D:/tmp/custom-runs.jsonl",
                "log_path": "D:/tmp/custom-run.log",
            },
        )()

        out_path, log_path = module.resolve_output_paths(args)

        self.assertEqual(str(out_path).replace("\\", "/"), "D:/tmp/custom-runs.jsonl")
        self.assertEqual(str(log_path).replace("\\", "/"), "D:/tmp/custom-run.log")

    def test_select_questions_respects_qid_order(self):
        module = _load_run_inference_module()
        questions = [
            {"qid": "Q01", "question": "a"},
            {"qid": "Q02", "question": "b"},
            {"qid": "Q03", "question": "c"},
        ]

        selected = module.select_questions(
            questions,
            qids=["Q03", "Q01"],
            offset=0,
            limit=None,
        )

        self.assertEqual([item["qid"] for item in selected], ["Q01", "Q03"])

    def test_select_questions_supports_resume_by_skipping_existing_qids(self):
        module = _load_run_inference_module()
        questions = [
            {"qid": "Q01", "question": "a"},
            {"qid": "Q02", "question": "b"},
            {"qid": "Q03", "question": "c"},
        ]

        selected = module.select_questions(
            questions,
            qids=None,
            offset=0,
            limit=None,
            existing_qids={"Q01", "Q03"},
            skip_existing=True,
        )

        self.assertEqual([item["qid"] for item in selected], ["Q02"])

    def test_build_request_payload_includes_session_id_for_followup_turns(self):
        module = _load_run_inference_module()

        payload = module._build_request_payload(
            {"question": "它对应的弃电量是多少？", "session_id": "session-01"}
        )

        self.assertEqual(payload["query"], "它对应的弃电量是多少？")
        self.assertEqual(payload["session_id"], "session-01")
        self.assertTrue(payload["options"]["include_sources"])

    def test_apply_response_payload_records_rewrite_metadata(self):
        module = _load_run_inference_module()
        record = {
            "retrieved_node_ids": [],
            "num_sources": 0,
            "activity_count": 0,
            "final_answer": "",
            "answer_node_ids": [],
            "tokens": {"input": 0, "output": 0, "total": 0},
            "runtime_metadata": {},
            "path_hit_node_ids": {},
            "pre_rerank_node_ids": [],
            "final_context_node_ids": [],
            "source_labels": [],
            "source_text_snippets": [],
            "session_id": None,
            "rewritten_query": None,
            "rewrite_reason": None,
            "latency_ms": 0,
        }
        payload = {
            "answer": "根据 [n0035]，W4S1 是最大弃电场景。",
            "sources": [
                {
                    "node_id": "d0_n0035",
                    "label": "W4S1",
                    "text_snippet": "W4S1 场景对应的弃电量为 173.7 MWh/日。",
                    "properties": {"entity_ids": ["d0_n0035"]},
                }
            ],
            "metadata": {
                "session_id": "session-01",
                "rewritten_query": "W4S1 对应的弃电量是多少？",
                "rewrite_reason": "coreference_resolution",
                "pre_rerank_node_ids": ["d0_n0035"],
                "final_context_node_ids": ["d0_n0035"],
                "path_hit_node_ids": {"kg": ["d0_n0035"]},
                "token_usage": {"prompt_tokens": 12, "completion_tokens": 8},
                "duration_ms": 321,
            },
        }

        module._apply_response_payload(record, payload)

        self.assertEqual(record["session_id"], "session-01")
        self.assertEqual(record["rewritten_query"], "W4S1 对应的弃电量是多少？")
        self.assertEqual(record["rewrite_reason"], "coreference_resolution")
        self.assertEqual(record["retrieved_node_ids"], ["n0035"])
        self.assertEqual(record["answer_node_ids"], ["n0035"])
        self.assertEqual(record["source_labels"], ["W4S1"])
        self.assertEqual(record["source_text_snippets"], ["W4S1 场景对应的弃电量为 173.7 MWh/日。"])
        self.assertEqual(record["latency_ms"], 321)

    def test_build_request_payload_includes_conversation_setup_messages(self):
        module = _load_run_inference_module()

        payload = module._build_request_payload(
            {
                "question": "它对应的弃电量是多少？",
                "session_id": "session-01",
            }
        )

        self.assertEqual(payload["session_id"], "session-01")
        self.assertNotIn("conversation_setup", payload)

    def test_prepare_conversation_setup_normalizes_setup_turns(self):
        module = _load_run_inference_module()

        normalized = module._prepare_conversation_setup(
            [
                {"question": "W4S1 是什么？"},
                {"query": "它对应的弃电量是多少？"},
                {"question": ""},
            ]
        )

        self.assertEqual(
            normalized,
            [
                {"query": "W4S1 是什么？"},
                {"query": "它对应的弃电量是多少？"},
            ],
        )

    def test_prepare_conversation_setup_returns_empty_for_missing_setup(self):
        module = _load_run_inference_module()

        self.assertEqual(module._prepare_conversation_setup(None), [])

    def test_prepare_setup_payloads_reuses_session_id(self):
        module = _load_run_inference_module()

        payloads = module._prepare_setup_payloads(
            {
                "session_id": "session-01",
                "conversation_setup": [
                    {"question": "W4S1 是什么？"},
                    {"query": "它对应的弃电量是多少？"},
                ],
            }
        )

        self.assertEqual(
            payloads,
            [
                {
                    "query": "W4S1 是什么？",
                    "session_id": "session-01",
                    "options": {"include_sources": True, "language": "ch"},
                },
                {
                    "query": "它对应的弃电量是多少？",
                    "session_id": "session-01",
                    "options": {"include_sources": True, "language": "ch"},
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
