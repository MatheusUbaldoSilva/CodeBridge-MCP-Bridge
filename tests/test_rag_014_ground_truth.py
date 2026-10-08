import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "rag014_dataset.jsonl"
GROUND_TRUTH = ROOT / "benchmarks" / "rag014_ground_truth.jsonl"


class Rag014GroundTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = [
            json.loads(line)
            for line in DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cls.ground_truth = [
            json.loads(line)
            for line in GROUND_TRUTH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_ground_truth_covers_all_100_queries(self):
        self.assertEqual(len(self.ground_truth), 100)
        dataset_ids = [row["id"] for row in self.dataset]
        truth_ids = [row["id"] for row in self.ground_truth]
        self.assertEqual(truth_ids, dataset_ids)

    def test_every_query_has_at_least_one_expected_source(self):
        for row in self.ground_truth:
            self.assertIsInstance(row["expected_paths"], list)
            self.assertGreaterEqual(len(row["expected_paths"]), 1)
            self.assertTrue(
                all(
                    isinstance(path, str) and path.strip()
                    for path in row["expected_paths"]
                )
            )

    def test_every_expected_source_exists_in_repository(self):
        missing = []
        for row in self.ground_truth:
            for relative in row["expected_paths"]:
                if not (ROOT / relative).exists():
                    missing.append((row["id"], relative))
        self.assertEqual(missing, [])

    def test_annotation_is_explicitly_manual(self):
        self.assertTrue(
            all(
                row["annotation_status"] == "MANUAL_RAG_014_B"
                for row in self.ground_truth
            )
        )

    def test_acceptance_policy_is_uniform(self):
        self.assertTrue(
            all(
                row["acceptance"] == "ANY_EXPECTED_PATH_IN_TOP_K"
                for row in self.ground_truth
            )
        )

    def test_ground_truth_ids_are_unique(self):
        ids = [row["id"] for row in self.ground_truth]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ground_truth_schema_is_stable(self):
        expected = {
            "id",
            "expected_paths",
            "acceptance",
            "annotation_status",
        }
        for row in self.ground_truth:
            self.assertEqual(set(row), expected)


if __name__ == "__main__":
    unittest.main()
