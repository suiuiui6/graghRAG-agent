import importlib.util
import unittest
from pathlib import Path


HELPERS_PATH = Path(__file__).with_name("run_inference_helpers.py")


def _load_helpers_module():
    spec = importlib.util.spec_from_file_location("run_inference_helpers", HELPERS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load helper module from {HELPERS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunInferenceHelpersTests(unittest.TestCase):
    def test_run_inference_uses_backend_rag_query_endpoint_instead_of_legacy_query_agent(self):
        source = Path(__file__).with_name("run_inference.py").read_text(encoding="utf-8")

        self.assertIn('"/api/v1/rag/query"', source)
        self.assertIn("TestClient", source)
        self.assertIn("from server import app", source)
        self.assertNotIn("def search_kg_by_type", source)
        self.assertNotIn("def get_entity_detail", source)
        self.assertNotIn("def get_kg_statistics", source)

    def test_extract_retrieved_node_ids_from_rag_sources(self):
        helpers = _load_helpers_module()

        sources = [
            {
                "chunk_id": "n0007",
                "source": "kg",
                "text_snippet": '{"entity": {"node_id": "n0007"}, "neighbors": [{"node_id": "n0009"}]}',
                "entity_ids": [],
                "metadata": {"entity_ids": ["n0008"]},
            },
            {
                "chunk_id": "c00001",
                "source": "vector",
                "text_snippet": 'Section cites [d0_n0010] and {"node_id":"d1_n0011"}',
                "entity_ids": ["d0_n0010"],
                "metadata": {},
            },
            {
                "chunk_id": "c00002",
                "source": "bm25",
                "text_snippet": "No ids here",
                "metadata": {"entity_ids": ["d0_n0008", "n0012"]},
            },
        ]

        self.assertEqual(
            helpers.extract_retrieved_node_ids_from_rag_sources(sources),
            ["n0007", "n0008", "n0009", "n0010", "n0011", "n0012"],
        )

    def test_extract_node_ids_normalizes_document_prefixed_ids(self):
        helpers = _load_helpers_module()

        self.assertEqual(
            helpers.extract_node_ids_from_text("见 d0_n0035、d1_n0042 和 n0007。"),
            ["n0007", "n0035", "n0042"],
        )

    def test_extract_retrieved_node_ids_from_endpoint_response_sources(self):
        helpers = _load_helpers_module()

        sources = [
            {
                "node_id": "c00031",
                "label": 'Section cites {"node_id":"d0_n0010"}',
                "properties": {"entity_ids": ["d1_n0011"], "source": "vector"},
            },
            {
                "node_id": "d0_n0035",
                "label": "W4S1 maximum curtailment scenario",
                "properties": {"entity_ids": [], "source": "kg"},
            },
        ]

        self.assertEqual(
            helpers.extract_retrieved_node_ids_from_rag_sources(sources),
            ["n0011", "n0010", "n0035"],
        )

    def test_extract_retrieved_node_ids_prefers_explicit_metadata_when_present(self):
        helpers = _load_helpers_module()

        self.assertEqual(
            helpers.extract_retrieved_node_ids_from_rag_sources(
                [],
                metadata={"retrieval_node_ids": ["n0035", "n0042"]},
            ),
            ["n0035", "n0042"],
        )

    def test_extract_retrieved_node_ids_prefers_pre_rerank_surface_over_broader_retrieval_surface(self):
        helpers = _load_helpers_module()

        self.assertEqual(
            helpers.extract_retrieved_node_ids_from_rag_sources(
                [],
                metadata={
                    "retrieval_node_ids": ["n0035", "n0042", "n0043"],
                    "pre_rerank_node_ids": ["n0035", "n0042"],
                },
            ),
            ["n0035", "n0042"],
        )

    def test_normalize_token_usage_prefers_context_total_when_needed(self):
        helpers = _load_helpers_module()

        token_usage = {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "context_tokens_used": 80,
        }

        self.assertEqual(
            helpers.normalize_token_usage(token_usage),
            {"input": 120, "output": 30, "total": 150},
        )


if __name__ == "__main__":
    unittest.main()
