"""Checks for controlled fixed-corpus gate remediation evidence."""
import json
from pathlib import Path
import unittest
B=Path(__file__).resolve().parents[1]/"benchmarks"

class QualityAblationTests(unittest.TestCase):
    def test_fixed_depths_and_gate_remains_blocked(self):
        report=json.loads((B/"rag017_quality_ablation.json").read_text(encoding="utf-8"))
        gate=json.loads((B/"rag017i_production_gate.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report["results"]),{"10","20","40"})
        targets={k:v["limit"] for k,v in gate["checks"].items() if k in ("recall_at_5","recall_at_10","mrr")}
        for depth,variants in report["results"].items():
            self.assertEqual(set(variants),{"baseline","diverse","deep"})
            for name,metrics in variants.items():
                self.assertLessEqual(metrics["recall5"],metrics["recall10"])
                self.assertTrue(0<=metrics["mrr"]<=1)
                self.assertFalse(all((metrics["recall5"]>=targets["recall_at_5"],metrics["recall10"]>=targets["recall_at_10"],metrics["mrr"]>=targets["mrr"])))
