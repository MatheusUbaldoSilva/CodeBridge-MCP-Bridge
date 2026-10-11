import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_preview_view import describe_incremental_preview


class PreviewViewTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"project_id": "demo",
                     "candidates": [{"path": path} for path in
                                    ("a.md", "b.py", "c.txt", "d.md")],
                     "denied_count": 2, "unsupported_count": 1}
        self.assessment = {"project_id": "demo",
                           "new_files": ["a.md"], "new_count": 1,
                           "modified_files": ["b.py"], "modified_count": 1,
                           "unchanged_files": ["c.txt"], "unchanged_count": 1,
                           "unknown_files": ["d.md"], "unknown_count": 1,
                           "safe_to_publish": True}

    def test_statuses_match_original_candidate_order(self):
        view = describe_incremental_preview(self.plan, self.assessment)
        self.assertEqual([entry["status"] for entry in view["rows"]],
                         ["NOVO", "ATUALIZAR", "SEM ALTERACAO", "VERIFICAR"])
        self.assertIn("2 protegidos", view["summary"])
        self.assertFalse(view["publish_enabled"])

    def test_rejects_missing_or_duplicate_classification(self):
        self.assessment["unknown_files"] = ["a.md"]
        with self.assertRaises(ValueError):
            describe_incremental_preview(self.plan, self.assessment)

    def test_rejects_cross_project_and_wrong_count(self):
        self.assessment["project_id"] = "other"
        with self.assertRaises(ValueError):
            describe_incremental_preview(self.plan, self.assessment)
        self.assessment["project_id"] = "demo"
        self.assessment["new_count"] = 2
        with self.assertRaises(ValueError):
            describe_incremental_preview(self.plan, self.assessment)


if __name__ == "__main__":
    unittest.main()
