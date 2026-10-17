import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture,OfflineFixtureError
import rag.runtime.offline_fixture_snapshot as module

class Lab04QdrantLateWalRace(unittest.TestCase):
    def test_wal_created_between_catalog_and_copy_rejects_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-qdrant-race-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","latewal","synthetic")])
            storage=next((root/"qdrant").rglob("storage.sqlite"))
            sidecar=Path(str(storage)+"-wal")
            original=module.shutil.copytree
            def late_sidecar(src,dst,*args,**kwargs):
                sidecar.write_bytes(b"synthetic-late-wal")
                return original(src,dst,*args,**kwargs)
            with patch.object(module.shutil,"copytree",side_effect=late_sidecar):
                with self.assertRaises(OfflineFixtureError):
                    capture_fixture(root,"late_wal")
            self.assertFalse((root/"offline-fixture-backups"/"late_wal").exists())
            self.assertEqual(list((root/"offline-fixture-backups").glob(".fixture-*")),[])
            sidecar.unlink()
            report=capture_fixture(root,"clean")
            self.assertEqual(report["state"],"LAB_FIXTURE_SNAPSHOT_ONLY")
            self.assertFalse(report["production_authorized"])

if __name__=="__main__":
    unittest.main()
