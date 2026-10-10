import json,tempfile,unittest
from pathlib import Path
class ReleaseEvidenceTests(unittest.TestCase):
 def test_saved_summary_cannot_approve_release(self):
  path=Path(__file__).resolve().parents[1]/"benchmarks"/"rag017_release_evidence_summary.json"
  data=json.loads(path.read_text(encoding="utf8"))
  self.assertIs(data["release_approved"],False)
  self.assertGreaterEqual(len(data["blockers"]),3)
  self.assertTrue(data["evidence"]["recovery"]["first_concurrent_request_failed"])
 def test_known_data_not_mislabeled_as_independent(self):
  path=Path(__file__).resolve().parents[1]/"benchmarks"/"rag017_release_evidence_summary.json"
  data=json.loads(path.read_text(encoding="utf8"))
  self.assertIn("not independent holdout",data["notes"])
