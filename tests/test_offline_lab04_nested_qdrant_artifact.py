import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

class Lab04NestedQdrantArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rag-lab04-nested-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","nested","synthetic")])
        self.artifact=self.root/"qdrant"/"checkpoint-lab"/"segments"/"segment-state.bin"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_bytes(b"SYNTHETIC-NOT-A-REAL-QDRANT-CHECKPOINT")

    def test_nested_artifact_survives_capture_restore(self):
        digest=hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        capture_fixture(self.root,"saved")
        result=restore_fixture_snapshot(self.root,"saved","restored")
        recovered=self.root/"offline-fixture-restores"/"restored"/"snapshot"/"qdrant"/"checkpoint-lab"/"segments"/"segment-state.bin"
        self.assertTrue(recovered.is_file())
        self.assertEqual(hashlib.sha256(recovered.read_bytes()).hexdigest(),digest)
        self.assertEqual(result["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
        self.assertFalse(result["production_authorized"])

    def test_nested_artifact_changed_after_capture_rejected(self):
        capture_fixture(self.root,"saved")
        artifact=self.root/"offline-fixture-backups"/"saved"/"snapshot"/"qdrant"/"checkpoint-lab"/"segments"/"segment-state.bin"
        artifact.write_bytes(artifact.read_bytes()+b"CORRUPTED")
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","denied")
        self.assertFalse((self.root/"offline-fixture-restores"/"denied").exists())

if __name__=="__main__":
    unittest.main()
