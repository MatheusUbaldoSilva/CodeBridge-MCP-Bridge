import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"benchmarks"/"rag017_qdrant_isolated_persistence.py").read_text(encoding="utf-8")
class QdrantIsolationContract(unittest.TestCase):
 def test_requires_explicit_isolated_prefix(self):
  self.assertIn("CodeBridge-RAG017-Qdrant-Probe-",SOURCE)
  self.assertIn("unsafe storage path",SOURCE)
 def test_reopen_checks_persisted_payload(self):
  self.assertIn('r[0].payload.get("marker")',SOURCE)
  self.assertIn("c.close()",SOURCE)
  self.assertIn("if not ok:raise SystemExit(2)",SOURCE)
