import unittest
from benchmarks.rag017_embedded_runtime_gate import inspect_runtime,REQUIRED

class EmbeddedRuntimeGateTests(unittest.TestCase):
 def test_missing_modules_block_install(self):
  result=inspect_runtime(lambda name:name not in {"numpy","qdrant_client","rag"})
  self.assertFalse(result["ready_for_rag"])
  self.assertEqual(set(result["missing"]),{"numpy","qdrant_client","rag"})
  self.assertFalse(result["production_approved"])
 def test_available_modules_still_do_not_approve_production(self):
  result=inspect_runtime(lambda name:True)
  self.assertTrue(result["ready_for_rag"])
  self.assertFalse(result["production_approved"])
  self.assertEqual(result["missing"],[])
