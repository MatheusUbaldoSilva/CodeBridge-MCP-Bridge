import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
import rag.runtime.offline_store_tree_catalog as catalog

class SyntheticStoreRaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="rag-lab02-e-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "race", "synthetic")])

    def assert_blocked(self, result):
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])

    def test_sidecar_created_after_initial_check_must_block(self):
        sidecar = self.root / "rag_index.sqlite3-wal"
        original = hashlib.sha256
        once = [False]
        def inject(*args, **kwargs):
            if not once[0]:
                once[0] = True
                sidecar.write_bytes(b"late-wal")
            return original(*args, **kwargs)
        with patch.object(catalog.hashlib, "sha256", side_effect=inject):
            result = catalog.catalog_synthetic_stores(self.root)
        self.assertTrue(sidecar.exists())
        self.assert_blocked(result)
        self.assertIn("SQLITE_SIDECAR_PRESENT", result["issues"])

    def test_external_vector_mutation_between_scans_blocks(self):
        baseline = catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(baseline["state"], "LAB_FILE_TREE_CATALOG_UNPROVEN")
        count = len(baseline["files"])
        vector = next(p for p in (self.root / "qdrant").rglob("*") if p.is_file())
        original = hashlib.sha256
        calls = [0]
        def inject(*args, **kwargs):
            calls[0] += 1
            if calls[0] == count + 1:
                process = subprocess.run(
                    [sys.executable, "-c",
                     "import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.write_bytes(p.read_bytes()+b'changed')",
                     str(vector)], capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
            return original(*args, **kwargs)
        with patch.object(catalog.hashlib, "sha256", side_effect=inject):
            result = catalog.catalog_synthetic_stores(self.root)
        self.assert_blocked(result)
        self.assertIn("FILE_TREE_CHANGED_DURING_CATALOG", result["issues"])

if __name__ == "__main__":
    unittest.main()
