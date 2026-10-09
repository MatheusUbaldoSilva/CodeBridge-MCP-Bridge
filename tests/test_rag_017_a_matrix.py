"""Regression guards for the RAG-017-A diagnostic artifacts."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BENCH=ROOT/"benchmarks"
def load(name):
    return json.loads((BENCH/name).read_text(encoding="utf-8"))
def load_jsonl(name):
    return [json.loads(line) for line in (BENCH/name).read_text(encoding="utf-8").splitlines() if line.strip()]

class TestRag017AMatrix(unittest.TestCase):
    def test_all_queries_have_provenance_and_component_rankings(self):
        rows=load("rag017_failure_matrix.json")["queries"]
        queries=load_jsonl("rag014_dataset.jsonl")
        expected=load_jsonl("rag014_ground_truth.jsonl")
        self.assertEqual(len(rows),100)
        self.assertEqual({r["id"] for r in rows},{r["id"] for r in queries})
        self.assertEqual({r["id"] for r in rows},{r["id"] for r in expected})
        for row in rows:
            self.assertTrue(row["query"])
            self.assertTrue(row["route"] in {"CODE","TEXT","HYBRID","LEXICAL_ONLY"})
            self.assertTrue(row["expected_sources"])
            for key in ("lexical_top10","text_vector_top10","code_vector_top10","rrf_top10","final_top10"):
                self.assertIsInstance(row[key],list)
                self.assertLessEqual(len(row[key]),10)
            self.assertTrue(row["failure_reason"] or row["first_expected_rank"] is not None)

    def test_metrics_derive_from_first_expected_rank(self):
        report=load("rag017_failure_matrix.json")
        rows=report["queries"]
        m=report["metrics"]
        self.assertEqual(m["query_count"],len(rows))
        self.assertEqual(m["hit_at_5"],sum(r["first_expected_rank"] is not None and r["first_expected_rank"]<=5 for r in rows))
        self.assertEqual(m["hit_at_10"],sum(r["first_expected_rank"] is not None for r in rows))
        self.assertAlmostEqual(m["mrr"],sum(1/r["first_expected_rank"] for r in rows if r["first_expected_rank"])/len(rows))
        self.assertEqual(len(load("rag017_component_trace.json")),100)
        self.assertEqual(load("rag017_replay_latest.json")["metrics"]["recall_at_10"],m["hit_at_10"]/100)

if __name__ == "__main__":
    unittest.main()
