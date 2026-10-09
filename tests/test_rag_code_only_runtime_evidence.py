"""Recorded code-only latency gate remains exploratory."""
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"benchmarks"
class CodeOnlyRuntimeEvidence(unittest.TestCase):
 def test_smoke_measurements(self):
  first=json.loads((ROOT/"rag017_code_only_runtime_smoke.json").read_text(encoding="utf8"))
  extended=json.loads((ROOT/"rag017_code_only_extended_smoke.json").read_text(encoding="utf8"))
  self.assertEqual(first["sample_count"],5)
  self.assertEqual(extended["sample"],12)
  self.assertEqual(extended["warm_sample"],11)
  self.assertLess(extended["warm_p95_observed_ms"],1000)
  self.assertEqual(extended["production_gate"],"BLOCKED")
 def test_code_only_quality_known_set(self):
  r=json.loads((ROOT/"rag017_code_only_ablation.json").read_text(encoding="utf8"))
  self.assertFalse(r["holdout_independent"])
  code=r["results"]["code_only"]
  self.assertGreaterEqual(code["recall_at_5"],.8)
  self.assertGreaterEqual(code["recall_at_10"],.9)
  self.assertGreaterEqual(code["mrr"],.6)
