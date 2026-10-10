import tempfile,unittest
from pathlib import Path
from benchmarks.rag017_full_rollback_preflight import inspect
class FullRollbackPreflightTests(unittest.TestCase):
 def test_real_installer_is_blocked_without_verified_vm(self):
  root=Path(__file__).resolve().parents[1]
  x=inspect(root/"installer"/"CodeBridge.nsi")
  self.assertTrue(x["side_effects_present"])
  self.assertFalse(x["host_execution_allowed"])
  self.assertFalse(x["rollback_full_test_allowed"])
  self.assertFalse(x["rollback_full_verified"])
 def test_safe_recipe_does_not_imply_vm(self):
  root=Path(__file__).resolve().parents[1]
  x=inspect(root/"installer"/"RAG017_Isolated_Test.nsi")
  self.assertFalse(x["side_effects_present"])
  self.assertFalse(x["rollback_full_test_allowed"])
