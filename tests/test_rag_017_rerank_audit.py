"""Invariant checks for the RAG-017 rerank exploration."""
import json
from pathlib import Path
import unittest
B=Path(__file__).resolve().parents[1]/"benchmarks"
class RerankAuditTests(unittest.TestCase):
    def test_corpus_expected_paths_exist(self):
        r=json.loads((B/"rag017_ground_truth_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(r["expected_fully_absent_queries"],0)
        self.assertEqual(r["missing"],[])
    def test_all_variants_do_not_pass_frozen_gate(self):
        r=json.loads((B/"rag017_quality_rerank_exploration.json").read_text(encoding="utf-8"))
        thresholds=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))["decision"]["thresholds"]
        self.assertEqual(len(r["results"]),15)
        for result in r["results"].values():
            self.assertFalse(result["recall5"]>=thresholds["recall_at_5_min"] and result["recall10"]>=thresholds["recall_at_10_min"] and result["mrr"]>=thresholds["mrr_min"])
