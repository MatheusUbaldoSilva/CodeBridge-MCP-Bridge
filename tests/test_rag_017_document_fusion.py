"""Ensure document-fusion diagnostic remains honest about the production gate."""
import json
import unittest
from pathlib import Path
B=Path(__file__).resolve().parents[1]/"benchmarks"

class DocumentFusionAuditTests(unittest.TestCase):
    def test_no_exploratory_variant_passes_all_thresholds(self):
        data=json.loads((B/"rag017_document_fusion_ablation.json").read_text(encoding="utf-8"))
        floor=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))["decision"]["thresholds"]
        self.assertEqual(len(data["results"]),28)
        for metrics in data["results"].values():
            self.assertFalse(
                metrics["recall5"]>=floor["recall_at_5_min"]
                and metrics["recall10"]>=floor["recall_at_10_min"]
                and metrics["mrr"]>=floor["mrr_min"]
            )
