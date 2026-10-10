import tempfile,unittest
from pathlib import Path
from benchmarks.rag017_vm_snapshot_manifest import capture
class VMManifestTests(unittest.TestCase):
 def test_refuses_unqualified_destination(self):
  with tempfile.TemporaryDirectory() as t:
   x=Path(t)/"not-disposable";x.mkdir()
   with self.assertRaises(ValueError):capture(x,Path(t)/"snap.json")
 def test_records_file_digests_without_claiming_full_snapshot(self):
  with tempfile.TemporaryDirectory() as t:
   x=Path(t)/"CodeBridge-RAG017-VMTest-canary";x.mkdir()
   (x/"canary.txt").write_text("baseline",encoding="utf-8")
   out=capture(x,Path(t)/"snapshot.json")
   self.assertEqual(len(out["files"]),1)
   self.assertFalse(out["vm_snapshot_verified"])
   self.assertFalse(out["registry_snapshot_verified"])
