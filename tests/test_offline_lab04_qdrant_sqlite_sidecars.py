import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot,OfflineFixtureRestoreError

class Lab04RealQdrantSQLiteSidecars(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-qdrant-sqlite-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","storage","synthetic")])
        self.storage=next(p for p in (self.root/"qdrant").rglob("storage.sqlite") if p.is_file())

    def test_internal_sqlite_sidecars_block_capture(self):
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                sidecar=Path(str(self.storage)+suffix)
                sidecar.write_bytes(b"synthetic-sidecar")
                try:
                    with self.assertRaises(OfflineFixtureError):
                        capture_fixture(self.root,"refused")
                    self.assertFalse((self.root/"offline-fixture-backups"/"refused").exists())
                finally:
                    sidecar.unlink()

    def test_internal_sqlite_sidecars_block_restore(self):
        capture_fixture(self.root,"clean")
        relative=self.storage.relative_to(self.root)
        restored_storage=self.root/"offline-fixture-backups"/"clean"/"snapshot"/relative
        for suffix in ("-wal","-shm","-journal"):
            with self.subTest(suffix=suffix):
                sidecar=Path(str(restored_storage)+suffix)
                sidecar.write_bytes(b"synthetic-sidecar")
                try:
                    with self.assertRaises(OfflineFixtureRestoreError):
                        restore_fixture_snapshot(self.root,"clean","refused")
                    self.assertFalse((self.root/"offline-fixture-restores"/"refused").exists())
                finally:
                    sidecar.unlink()

if __name__=="__main__":
    unittest.main()
