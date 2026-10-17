import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
import rag.runtime.offline_store_tree_catalog as catalog

class SyntheticToctouTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="rag-lab02-f-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "toctou", "synthetic")])

    def test_qdrant_file_replaced_between_scans_blocks(self):
        vector = next(p for p in (self.root / "qdrant").rglob("*") if p.is_file())
        original = catalog.os.scandir
        calls = [0]
        def changed(path):
            if Path(path) == self.root / "qdrant":
                calls[0] += 1
                if calls[0] == 2:
                    vector.unlink()
                    vector.mkdir()
            return original(path)
        with patch.object(catalog.os, "scandir", side_effect=changed):
            result = catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])

    def test_qdrant_redirect_between_scans_blocks(self):
        vectors = self.root / "qdrant"
        moved = self.root / "relocated"
        original = catalog.os.scandir
        calls = [0]
        def changed(path):
            if Path(path) == vectors:
                calls[0] += 1
                if calls[0] == 2:
                    vectors.rename(moved)
                    vectors.symlink_to(moved, target_is_directory=True)
            return original(path)
        with patch.object(catalog.os, "scandir", side_effect=changed):
            result = catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["production_quiescence_proven"])

if __name__ == "__main__":
    unittest.main()
