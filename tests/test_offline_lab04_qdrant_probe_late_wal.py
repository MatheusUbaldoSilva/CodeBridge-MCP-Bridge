import hashlib
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
import rag.runtime.offline_store_tree_catalog as catalog
import rag.runtime.offline_store_handle_probe as probe

class LateQdrantSidecarsInProbes(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-probe-race-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","race","synthetic")])
        storage=next((self.root/"qdrant").rglob("storage.sqlite"))
        self.wal=Path(str(storage)+"-wal")
    def test_late_wal_during_catalog_hash_is_blocked(self):
        real=hashlib.sha256
        triggered=[False]
        def inject(*args,**kwargs):
            if not triggered[0]:
                triggered[0]=True
                self.wal.write_bytes(b"late-wal")
            return real(*args,**kwargs)
        with patch.object(catalog.hashlib,"sha256",side_effect=inject):
            result=catalog.catalog_synthetic_stores(self.root)
        self.assertTrue(triggered[0])
        self.assertEqual(result["state"],"BLOCKED")
        self.assertFalse(result["copy_authorized"])
    def test_late_wal_during_handle_fingerprints_is_blocked(self):
        real=hashlib.sha256
        triggered=[False]
        def inject(*args,**kwargs):
            if not triggered[0]:
                triggered[0]=True
                self.wal.write_bytes(b"late-wal")
            return real(*args,**kwargs)
        with patch.object(probe.hashlib,"sha256",side_effect=inject):
            result=probe.inspect_fixture_handles(self.root)
        self.assertTrue(triggered[0])
        self.assertEqual(result["state"],"BLOCKED")
        self.assertFalse(result["all_handles_closed"])
if __name__=="__main__":
    unittest.main()
