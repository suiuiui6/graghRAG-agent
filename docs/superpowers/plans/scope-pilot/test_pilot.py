"""Software checks only; never report these fixtures as model performance."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


class PilotChecks(unittest.TestCase):
    def load(self):
        path = HERE / "pilot.py"
        self.assertTrue(path.is_file(), "offline pilot implementation is missing")
        spec = importlib.util.spec_from_file_location("scope_pilot", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_gold_anchors_and_scope(self):
        p = self.load()
        data = p.load_gold()
        self.assertEqual(len(data["questions"]), 9)
        self.assertEqual(sum(len(q["items"]) for q in data["questions"]), 31)
        self.assertEqual(p.validate_gold(data), [])

    def test_scope_reads_are_complete_not_gold_assembled(self):
        p = self.load()
        data = p.load_gold()
        q = next(q for q in data["questions"] if q["id"] == "D1-COST")
        parts, status = p.contexts(data, q, "B3", 8192)
        self.assertEqual(status, "READY")
        text = "\n".join(c["text"] for c in parts)
        self.assertIn("9023", text)  # scope includes non-gold abstract facts
        self.assertNotIn("168元", text)
        self.assertEqual(p.anchor_coverage(q, parts)["covered"], 5)

    def test_budget_blocks_full_scope_instead_of_silent_truncation(self):
        p = self.load()
        data = p.load_gold()
        q = next(q for q in data["questions"] if q["id"] == "D1-COST")
        parts, status = p.contexts(data, q, "B3", 2)
        self.assertEqual(status, "BUDGET_EXCEEDED")
        self.assertEqual(parts, [])

    def test_strong_filter_uses_available_budget_not_arbitrary_top3(self):
        p = self.load()
        data = p.load_gold()
        q = next(q for q in data["questions"] if q["id"] == "D1-FIG")
        parts, status = p.contexts(data, q, "B2", 8192)
        self.assertEqual(status, "READY")
        self.assertEqual(p.anchor_coverage(q, parts)["covered"], 6)

    def test_empty_gold_is_not_perfect_retrieval(self):
        p = self.load()
        self.assertIsNone(p.anchor_coverage({"items": []}, [])['recall'])

    def test_coverage_is_not_numeric_presence(self):
        p = self.load()
        q = {"items": [{"anchor": "72吨/日，18/24场景全满足，7111元/吨"}]}
        self.assertEqual(p.anchor_coverage(q, [{"text": "7111元/吨"}])["covered"], 0)

    def test_generation_failures_have_no_item_score(self):
        p = self.load()
        self.assertIsNone(p.score_adjudication({"items": []}, {"status": "ERROR"})["recall"])

    def test_empty_scope_requires_correct_absence_statement(self):
        p = self.load()
        row = {"status": "OK", "claims": [], "exhaustive_claim": False,
               "scope_review_complete": True, "empty_scope_correct": False}
        self.assertFalse(p.score_adjudication({"items": []}, row)["complete_correct_set"])

    def test_duplicate_matches_do_not_inflate_recall(self):
        p = self.load()
        q = {"items": [{"id": "A"}, {"id": "B"}]}
        row = {"status": "OK", "claims": [
            {"gold_id": "A", "condition_correct": True, "role_correct": True, "support_correct": True, "in_scope": True},
            {"gold_id": "A", "condition_correct": True, "role_correct": True, "support_correct": True, "in_scope": True},
            {"gold_id": "B", "condition_correct": False, "role_correct": True, "support_correct": True, "in_scope": True}],
            "exhaustive_claim": True, "scope_review_complete": True}
        score = p.score_adjudication(q, row)
        self.assertEqual(score["recall"], .5)
        self.assertTrue(score["false_exhaustive"])


if __name__ == "__main__":
    unittest.main()
