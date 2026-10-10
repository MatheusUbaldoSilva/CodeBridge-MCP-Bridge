import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/"benchmarks"/"rag017_qdrant_crash_recovery.py").read_text(encoding="utf-8")
class CrashCanaryContract(unittest.TestCase):
 def test_refuses_non_disposable_path(self):
  self.assertIn('path.name.startswith("CodeBridge-RAG017-CrashProbe-")',S)
  self.assertIn('path.parent.name.lower()!="temp"',S)
 def test_canary_is_verified_after_restart(self):
  self.assertIn('ready_to_kill',S)
  self.assertIn('after-abrupt-kill',S)
  self.assertIn('if not success:raise SystemExit(2)',S)
