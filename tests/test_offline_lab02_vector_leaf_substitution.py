import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles
from rag.runtime.offline_store_tree_catalog import catalog_synthetic_stores

class VectorLeafSubstitution(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix="rag-leaf-")
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("alpha","one","synthetic"),("beta","two","synthetic")])

    def test_empty_directory_replacing_leaf_blocks_both(self):
        vectors=sorted(p for p in (self.root/"qdrant").rglob("*") if p.is_file())
        self.assertGreaterEqual(len(vectors),2)
        vectors[0].unlink()
        vectors[0].mkdir()
        for inspect in (inspect_fixture_handles,catalog_synthetic_stores):
            with self.subTest(probe=inspect.__name__):
                result=inspect(self.root)
                self.assertEqual(result["state"],"BLOCKED")
                self.assertFalse(result["copy_authorized"])
                self.assertFalse(result["all_handles_closed"])
                self.assertFalse(result["production_quiescence_proven"])

if __name__=="__main__":
    unittest.main()
