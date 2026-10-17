import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles
from rag.runtime.offline_store_tree_catalog import catalog_synthetic_stores

@unittest.skipUnless(sys.platform == "win32", "Windows-only Qdrant handle lab")
class SyntheticQdrantHandles(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="rag-lab02-c-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "qdrant", "synthetic")])
        self.vector = next(p for p in (self.root / "qdrant").rglob("*") if p.is_file())

    def test_external_vector_writer_blocks_handle_probe(self):
        script = ("import sys,time;"
                  "f=open(sys.argv[1],'r+b',buffering=0);"
                  "print('READY',flush=True);"
                  "time.sleep(12)")
        child = subprocess.Popen([sys.executable, "-c", script, str(self.vector)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            blocked = inspect_fixture_handles(self.root)
            self.assertEqual(blocked["state"], "BLOCKED")
            self.assertFalse(blocked["copy_authorized"])
            self.assertFalse(blocked["all_handles_closed"])
            inventory = catalog_synthetic_stores(self.root)
            self.assertFalse(inventory["copy_authorized"])
            self.assertFalse(inventory["all_handles_closed"])
            self.assertFalse(inventory["production_quiescence_proven"])
        finally:
            child.terminate()
            child.communicate(timeout=10)
        after = inspect_fixture_handles(self.root)
        self.assertEqual(after["state"], "LAB_HANDLES_READABLE_UNPROVEN")
        self.assertFalse(after["copy_authorized"])

    def test_nested_qdrant_file_is_in_catalog_but_never_authorized(self):
        nested = self.root / "qdrant" / "segments" / "nested"
        nested.mkdir(parents=True)
        (nested / "vector.bin").write_bytes(b"synthetic-vector")
        result = catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"], "LAB_FILE_TREE_CATALOG_UNPROVEN")
        self.assertTrue(any("vector.bin" in p for p in result["files"]))
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])

    def test_empty_qdrant_directory_blocks(self):
        import shutil
        shutil.rmtree(self.root / "qdrant")
        (self.root / "qdrant").mkdir()
        result = inspect_fixture_handles(self.root)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])

if __name__ == "__main__":
    unittest.main()
