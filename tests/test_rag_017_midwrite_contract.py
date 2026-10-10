import unittest
from pathlib import Path
S=(Path(__file__).resolve().parents[1]/"benchmarks"/"rag017_qdrant_midwrite_probe.py").read_text(encoding="utf-8")
class MidwriteContract(unittest.TestCase):
 def test_disposable_only(self):
  self.assertIn("CodeBridge-RAG017-MidWrite-",S)
  self.assertIn("unsafe path",S)
 def test_baseline_is_durable_guard(self):
  self.assertIn('"committed":True',S)
  self.assertIn('baseline_intact',S)
  self.assertIn('if not passed:raise SystemExit(2)',S)
