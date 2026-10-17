import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

@unittest.skipUnless(sys.platform == "win32", "Windows filesystem link laboratory")
class Lab04QdrantLinkBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-links-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","links","synthetic")])

    def test_qdrant_hardlink_outside_root_blocks_capture(self):
        leaf=next(p for p in (self.root/"qdrant").rglob("*") if p.is_file())
        external=self.root.parent/"external-hardlink.bin"
        os.link(leaf,external)
        with self.assertRaises(OfflineFixtureError):
            capture_fixture(self.root,"unsafe_hardlink")
        self.assertFalse((self.root/"offline-fixture-backups"/"unsafe_hardlink").exists())

    def test_symlink_added_to_backup_blocks_restore(self):
        capture_fixture(self.root,"saved")
        outside=self.root.parent/"redirect-target.txt"
        outside.write_bytes(b"synthetic")
        link=self.root/"offline-fixture-backups"/"saved"/"snapshot"/"qdrant"/"external-link.txt"
        link.symlink_to(outside)
        with self.assertRaises(OfflineFixtureRestoreError):
            restore_fixture_snapshot(self.root,"saved","unsafe")
        self.assertFalse((self.root/"offline-fixture-restores"/"unsafe").exists())

if __name__=="__main__":
    unittest.main()
