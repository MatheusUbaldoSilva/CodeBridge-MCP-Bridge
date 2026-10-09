"""Audit source coverage and hierarchy results without relaxing production thresholds."""
import json
import unittest
from pathlib import Path
B=Path(__file__).resolve().parents[1]/"benchmarks"
class HierarchyAuditTests(unittest.TestCase):
 def test_coverage_monotone_and_oracle_not_quality(self):
  r=json.loads((B/"rag017_hierarchy_diagnostic.json").read_text(encoding="utf-8"))
  values=[r["candidate_coverage"][str(k)] for k in (5,10,20,32,64)]
  self.assertEqual(values,sorted(values))
  self.assertEqual(values[-1],0.96)
 def test_gate_remains_blocked(self):
  r=json.loads((B/"rag017_hierarchy_diagnostic.json").read_text(encoding="utf-8"))
  t=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))["decision"]["thresholds"]
  for metric in r["hierarchical"].values():
   self.assertFalse(metric["recall5"]>=t["recall_at_5_min"] and metric["recall10"]>=t["recall_at_10_min"] and metric["mrr"]>=t["mrr_min"])
