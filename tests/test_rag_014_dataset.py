import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "rag014_dataset.jsonl"

EXPECTED_COUNTS = {
    "code": 25,
    "docs": 25,
    "errors_audits": 20,
    "git": 10,
    "logs": 10,
    "ptbr_code": 10,
}


class Rag014DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [
            json.loads(line)
            for line in DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_dataset_has_exactly_100_queries(self):
        self.assertEqual(len(self.rows), 100)

    def test_category_distribution_matches_handoff(self):
        counts = Counter(row["category"] for row in self.rows)
        self.assertEqual(dict(counts), EXPECTED_COUNTS)

    def test_ids_are_unique_and_sequential(self):
        ids = [row["id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            ids,
            [
                f"rag014-{index:03d}"
                for index in range(1, 101)
            ],
        )

    def test_queries_are_unique_and_non_empty(self):
        queries = [row["query"] for row in self.rows]
        self.assertTrue(all(isinstance(q, str) and q.strip() for q in queries))
        self.assertEqual(len(queries), len(set(queries)))

    def test_ground_truth_is_explicitly_deferred_to_rag_014_b(self):
        self.assertTrue(
            all(
                row["ground_truth_status"] == "PENDING_RAG_014_B"
                for row in self.rows
            )
        )

    def test_ptbr_bucket_is_portuguese_and_only_that_bucket(self):
        for row in self.rows:
            expected_language = (
                "pt-BR"
                if row["category"] == "ptbr_code"
                else "en"
            )
            self.assertEqual(row["language"], expected_language)

    def test_rows_use_exact_public_schema(self):
        expected_keys = {
            "id",
            "category",
            "query",
            "language",
            "ground_truth_status",
        }
        for row in self.rows:
            self.assertEqual(set(row), expected_keys)


if __name__ == "__main__":
    unittest.main()
