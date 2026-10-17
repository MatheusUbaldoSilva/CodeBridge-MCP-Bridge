import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles

class StoreHandleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"codebridge-rag-generation-test"
        create_bundle(self.root,[("lab","test","synthetic data")])
    def test_normal_lab_probe_never_authorizes(self):
        r=inspect_fixture_handles(self.root)
        self.assertEqual(r["state"],"LAB_HANDLES_READABLE_UNPROVEN")
        self.assertGreaterEqual(r["files_checked"],3)
        self.assertFalse(r["copy_authorized"])
        self.assertFalse(r["all_handles_closed"])
    def test_sidecars_fail_closed(self):
        for ext in ("-wal","-shm","-journal"):
            with self.subTest(ext=ext):
                p=self.root/("rag_index.sqlite3"+ext)
                p.write_bytes(b"synthetic")
                r=inspect_fixture_handles(self.root)
                self.assertEqual(r["state"],"BLOCKED")
                self.assertIn("SQLITE_SIDECAR_PRESENT",r["issues"])
                p.unlink()
    def test_wrong_root_fails_closed(self):
        self.assertEqual(inspect_fixture_handles(self.root.parent)["state"],"BLOCKED")
    def test_missing_qdrant_fails_closed(self):
        import shutil
        shutil.rmtree(self.root/"qdrant")
        self.assertEqual(inspect_fixture_handles(self.root)["state"],"BLOCKED")
    def test_vector_symlink_is_rejected(self):
        (self.root/"qdrant"/"outside").symlink_to(self.root.parent,target_is_directory=True)
        r=inspect_fixture_handles(self.root)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("VECTOR_TREE_REDIRECTED",r["issues"])
    def test_detects_mismatched_fingerprints(self):
        from unittest.mock import patch
        import rag.runtime.offline_store_handle_probe as probe
        original=probe._hash_tree
        counts=[0]
        def changed(root):
            result=original(root)
            counts[0]+=1
            if counts[0]>1:
                result["synthetic-change"]="0"*64
            return result
        with patch.object(probe,"_hash_tree",side_effect=changed):
            result=inspect_fixture_handles(self.root)
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("STORES_CHANGED_DURING_READ",result["issues"])
        self.assertFalse(result["copy_authorized"])

    def test_external_open_writer_fails_closed(self):
        import subprocess
        script=("import sys,time;"
                "f=open(sys.argv[1],'r+b',buffering=0);"
                "print('READY',flush=True);"
                "time.sleep(10)")
        p=subprocess.Popen([sys.executable,"-c",script,str(self.root/"rag_index.sqlite3")],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),"READY")
            r=inspect_fixture_handles(self.root)
            self.assertEqual(r["state"],"BLOCKED")
            self.assertFalse(r["copy_authorized"])
        finally:
            p.terminate()
            p.communicate(timeout=10)
if __name__=="__main__":
    unittest.main()
