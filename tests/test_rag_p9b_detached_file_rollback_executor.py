import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from installer.rag_p9b_detached_file_rollback_executor import restore_files_detached


class FileRollbackTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.installed=self.root/"installed"
        (self.installed/"rag").mkdir(parents=True)
        (self.installed/"rag"/"old.py").write_bytes(b"updated")
        (self.installed/"rag"/"new.py").write_bytes(b"created")
        self.archive=self.root/"backup.zip"
        with ZipFile(self.archive,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "installed_root":str(self.installed),
                "targets":["rag/old.py","rag/new.py"],
                "existing":{"rag/old.py":{"sha256":hashlib.sha256(b"original").hexdigest()}}}))
            z.writestr("old/rag/old.py",b"original")
        self.log=[]
        self.options=dict(snapshot=self.archive,installed=self.installed,
            expected_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            expected_new_hashes={"rag/new.py":hashlib.sha256(b"created").hexdigest()},
            preimage=self.root/"preimage",preimage_sha256="a"*64,
            journal_path=self.root/"journal",
            journal=lambda state,info:self.log.append(state),
            external=True,execute=True,
            gate=lambda **kw: {"state":"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY"},
            stopped_probe=lambda *a:{"state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
    def run_it(self,**overrides):
        return restore_files_detached(**(self.options|overrides))
    def test_synthetic_full_file_rollback(self):
        r=self.run_it()
        self.assertEqual(r["state"],"DETACHED_FILES_RESTORED_SHELL_PENDING")
        self.assertTrue(r["verified"])
        self.assertEqual((self.installed/"rag"/"old.py").read_bytes(),b"original")
        self.assertFalse((self.installed/"rag"/"new.py").exists())
        self.assertIn("SHELL_PRODUCTION_FILE_RESTORED",self.log)
    def test_no_mutation_without_external_execution(self):
        self.assertEqual(self.run_it(execute=False)["reason"],"EXTERNAL_EXECUTION_AND_JOURNAL_REQUIRED")
        self.assertEqual((self.installed/"rag"/"old.py").read_bytes(),b"updated")
    def test_reject_foreign_new_file(self):
        (self.installed/"rag"/"new.py").write_bytes(b"foreign")
        self.assertEqual(self.run_it()["reason"],"NEW_TARGET_NOT_OWNED")
        self.assertEqual((self.installed/"rag"/"old.py").read_bytes(),b"updated")
    def test_recheck_blocks_active_process(self):
        r=self.run_it(stopped_probe=lambda *a:{"state":"POSTSTOP_UNVERIFIED"})
        self.assertEqual(r["reason"],"POSTSTOP_RECHECK_FAILED")
        self.assertEqual((self.installed/"rag"/"old.py").read_bytes(),b"updated")
    def test_crash_mid_file_restore_requires_review(self):
        def boom(*args):
            raise OSError("simulated interruption")
        r=self.run_it(replace_file=boom)
        self.assertEqual(r["state"],"DETACHED_FILE_RESTORE_REVIEW_REQUIRED")
        self.assertIn("SHELL_PRODUCTION_FILE_RESTORE_FAILED",self.log)
        self.assertEqual((self.installed/"rag"/"new.py").read_bytes(),b"created")

if __name__=="__main__":
    unittest.main()
