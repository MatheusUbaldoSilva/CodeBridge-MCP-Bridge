import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
import rag.runtime.offline_store_tree_catalog as catalog

class SyntheticStoreTreeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("alpha","note","hello"),("beta","text","world")])
    def test_all_three_stores_enumerated_without_authorization(self):
        result=catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"],"LAB_FILE_TREE_CATALOG_UNPROVEN")
        self.assertIn("rag_index.sqlite3",result["files"])
        self.assertIn("rag-index-manifest.json",result["files"])
        self.assertTrue(any(key.startswith("qdrant/") for key in result["files"]))
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
    def test_sqlite_sidecar_blocks(self):
        path=self.root/"rag_index.sqlite3-wal"
        path.write_bytes(b"synthetic")
        result=catalog.catalog_synthetic_stores(self.root)
        self.assertIn("SQLITE_SIDECAR_PRESENT",result["issues"])
    def test_redirected_vector_directory_blocks(self):
        root=self.root/"qdrant"
        moved=self.root/"original_qdrant"
        root.rename(moved)
        root.symlink_to(moved,target_is_directory=True)
        result=catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"],"BLOCKED")
    def test_hardlinked_vector_file_blocks(self):
        target=next(p for p in (self.root/"qdrant").rglob("*") if p.is_file())
        os.link(target,self.root/"linked-copy")
        result=catalog.catalog_synthetic_stores(self.root)
        self.assertEqual(result["state"],"BLOCKED")
    def test_new_file_during_hashing_blocks(self):
        original=hashlib.sha256
        count=[0]
        def mutation(*args,**kwargs):
            count[0]+=1
            if count[0]==1:
                (self.root/"qdrant"/"late-entry").write_bytes(b"new")
            return original(*args,**kwargs)
        with patch.object(catalog.hashlib,"sha256",side_effect=mutation):
            result=catalog.catalog_synthetic_stores(self.root)
        self.assertIn("FILE_TREE_CHANGED_DURING_CATALOG",result["issues"])
    def test_missing_directory_blocks(self):
        import shutil
        shutil.rmtree(self.root/"qdrant")
        self.assertEqual(catalog.catalog_synthetic_stores(self.root)["state"],"BLOCKED")
    def test_file_count_limit_blocks(self):
        result=catalog.catalog_synthetic_stores(self.root,max_files=3)
        if result["files_checked"]>0:
            self.assertLessEqual(result["files_checked"],3)
        self.assertFalse(result["copy_authorized"])
    def test_wrong_root_blocks(self):
        self.assertEqual(catalog.catalog_synthetic_stores(self.root.parent)["state"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
