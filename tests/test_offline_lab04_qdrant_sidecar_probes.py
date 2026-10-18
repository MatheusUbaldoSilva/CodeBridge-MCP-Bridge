import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_tree_catalog import catalog_synthetic_stores
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles

class InternalQdrantSidecarProbeMatrix(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="rag-lab04-probes-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","probes","synthetic")])
        self.sqlite=next((self.root/"qdrant").rglob("storage.sqlite"))
    def test_all_qdrant_sqlite_sidecars_block_both_probes(self):
        for suffix in ("-wal","-shm","-journal"):
            path=Path(str(self.sqlite)+suffix)
            path.write_bytes(b"synthetic")
            try:
                for probe in (catalog_synthetic_stores,inspect_fixture_handles):
                    with self.subTest(suffix=suffix,probe=probe.__name__):
                        result=probe(self.root)
                        self.assertEqual(result["state"],"BLOCKED")
                        self.assertFalse(result["copy_authorized"])
                        self.assertFalse(result["all_handles_closed"])
                        self.assertFalse(result["production_quiescence_proven"])
            finally:
                path.unlink()
if __name__=="__main__":
    unittest.main()
