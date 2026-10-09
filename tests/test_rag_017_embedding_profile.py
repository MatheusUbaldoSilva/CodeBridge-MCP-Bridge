"""Regression audit for measured Jina inference budget."""
import json
import unittest
from pathlib import Path
FILE=Path(__file__).resolve().parents[1]/"benchmarks"/"rag017_embedding_model_profile.json"
class EmbeddingProfileAudit(unittest.TestCase):
 def test_warm_inference_is_above_threshold(self):
  report=json.loads(FILE.read_text(encoding="utf-8"))
  samples=report["results"]
  self.assertEqual(len(samples),5)
  for item in samples[1:]:
   self.assertGreater(sum(stage["ms"] for stage in item["steps"].values()),1000)
  self.assertEqual(report["production_gate"],"BLOCKED")
 def test_gpu_samples_within_device_capacity(self):
  report=json.loads(FILE.read_text(encoding="utf-8"))
  for item in report["results"]:
   self.assertLessEqual(item["gpu_memory_mib_and_util_percent"][0],6144)
   self.assertGreater(item["gpu_memory_mib_and_util_percent"][0],5000)
