"""RAG-017-D diagnostic integrity and route coverage."""
import json
from pathlib import Path
import unittest

BENCH=Path(__file__).resolve().parents[1]/"benchmarks"

class TestRag017DVectorDiagnostic(unittest.TestCase):
    def test_every_query_has_vector_evidence(self):
        data=json.loads((BENCH/"rag017d_vector_diagnostic.json").read_text(encoding="utf-8"))
        rows=data["queries"]
        self.assertEqual(len(rows),100)
        self.assertEqual(len({r["id"] for r in rows}),100)
        for row in rows:
            self.assertTrue(row["expected"])
            self.assertIn(row["route"],("CODE","TEXT","HYBRID"))
            self.assertLessEqual(len(row["text_top10"]),10)
            self.assertLessEqual(len(row["code_top10"]),10)
            self.assertIsInstance(row["expected_in_vector"],bool)

    def test_counts_derive_from_observed_rankings(self):
        data=json.loads((BENCH/"rag017d_vector_diagnostic.json").read_text(encoding="utf-8"))
        rows=data["queries"]
        matches=0
        for row in rows:
            ranked=row["text_top10"] if row["route"]=="TEXT" else row["code_top10"] if row["route"]=="CODE" else row["text_top10"]+row["code_top10"]
            hit=bool(set(row["expected"]).intersection(ranked))
            self.assertEqual(hit,row["expected_in_vector"])
            self.assertEqual(row["top10_unique_path_count"],len(set(ranked)))
            matches+=hit
        self.assertEqual(matches,data["counts"]["expected_in_vector_top10"])
        self.assertEqual(100-matches,data["counts"]["expected_absent_vector_top10"])

if __name__=="__main__":
    unittest.main()
