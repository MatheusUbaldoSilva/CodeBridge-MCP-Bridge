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

    def test_external_manifest_writer_fails_closed(self):
        self._assert_writer_blocks(self.root/"rag-index-manifest.json")

    def test_external_qdrant_writer_fails_closed(self):
        vector=next(x for x in (self.root/"qdrant").rglob("*") if x.is_file())
        self._assert_writer_blocks(vector)

    def _assert_writer_blocks(self, source):
        import subprocess
        script=("import sys,time;"
                "f=open(sys.argv[1],'r+b',buffering=0);"
                "print('READY',flush=True);"
                "time.sleep(10)")
        p=subprocess.Popen([sys.executable,"-c",script,str(source)],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),"READY")
            result=inspect_fixture_handles(self.root)
            self.assertEqual(result["state"],"BLOCKED")
            self.assertFalse(result["copy_authorized"])
        finally:
            p.terminate()
            p.communicate(timeout=10)

    def test_exited_parent_with_orphan_writer_still_blocks(self):
        import subprocess
        import time
        sqlite_path=self.root/"rag_index.sqlite3"
        ready=self.root/"child-ready.txt"
        writer=("import sys,time;"
                "f=open(sys.argv[1],'r+b',buffering=0);"
                "open(sys.argv[2],'w').write('ready');"
                "time.sleep(3)")
        parent=("import subprocess,sys;"
                "p=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "print(p.pid,flush=True)")
        launch=subprocess.run([sys.executable,"-c",parent,writer,str(sqlite_path),str(ready)],
                              capture_output=True,text=True,timeout=10)
        self.assertEqual(launch.returncode,0,launch.stderr)
        child_pid=int(launch.stdout.strip())
        try:
            for _ in range(40):
                if ready.exists():
                    break
                time.sleep(0.05)
            self.assertTrue(ready.exists())
            result=inspect_fixture_handles(self.root)
            self.assertEqual(result["state"],"BLOCKED")
            self.assertFalse(result["copy_authorized"])
        finally:
            # The synthetic child exits on its own; no PID is killed.
            time.sleep(3.2)
            released=inspect_fixture_handles(self.root)
            self.assertEqual(released["state"],"LAB_HANDLES_READABLE_UNPROVEN")

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
