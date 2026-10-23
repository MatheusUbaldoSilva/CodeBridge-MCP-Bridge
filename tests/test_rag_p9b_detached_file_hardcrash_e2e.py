"""Hard-exit of real file-only rollback on an ephemeral lab fixture."""
import hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from zipfile import ZipFile
from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal
from installer.rag_p9b_detached_file_rollback_executor import restore_files_detached


class HardExitFileRollbackTests(unittest.TestCase):
    def test_after_atomic_replacement_hard_exit_then_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            installed=root/"installed"
            (installed/"rag").mkdir(parents=True)
            old=installed/"rag"/"old.py"
            new=installed/"rag"/"new.py"
            old.write_bytes(b"updated")
            new.write_bytes(b"candidate")
            backup=root/"backup.zip"
            with ZipFile(backup,"w") as z:
                z.writestr("manifest.json",json.dumps({
                    "installed_root":str(installed),
                    "targets":["rag/old.py","rag/new.py"],
                    "existing":{"rag/old.py":{
                        "sha256":hashlib.sha256(b"original").hexdigest()}}}))
                z.writestr("old/rag/old.py",b"original")
            journal=root/"journal.jsonl"
            initial=RollbackJournal(journal)
            initial("SHELL_NSIS_FULL_SCOPE_INTERRUPTED",{})
            worker=root/"crash_worker.py"
            worker.write_text("""
import hashlib,os,sys
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_detached_file_rollback_executor import restore_files_detached
from installer.rag_p9b_file_restore_executor_lab import _replace_old_file_atomically
root=Path(sys.argv[1]); target=root/"installed"
backup=root/"backup.zip"; journal=root/"journal.jsonl"
def crash(target,data):
    _replace_old_file_atomically(target,data)
    os._exit(75)
restore_files_detached(
    snapshot=backup,installed=target,
    expected_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
    expected_new_hashes={"rag/new.py":hashlib.sha256(b"candidate").hexdigest()},
    preimage=root/"preimage",preimage_sha256="a"*64,
    journal_path=journal,journal=RollbackJournal.resume(journal),
    external=True,execute=True,
    gate=lambda **kw:{"state":"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY"},
    stopped_probe=lambda *a:{"state":"POSTSTOP_OBSERVED_ONLY",
                             "observed_stopped":True},
    replace_file=crash)
""",encoding="utf-8")
            repo=str(Path(__file__).resolve().parents[1])
            env=dict(os.environ)
            env["PYTHONPATH"]=repo+os.pathsep+env.get("PYTHONPATH","")
            process=subprocess.run([sys.executable,str(worker),str(root)],
                cwd=repo,env=env,capture_output=True,timeout=15)
            self.assertEqual(process.returncode,75,process.stderr)
            self.assertEqual(old.read_bytes(),b"original")
            self.assertEqual(new.read_bytes(),b"candidate")
            self.assertEqual(read_journal(journal)["last_state"],
                             "SHELL_PRODUCTION_FILE_BEFORE_REPLACE")
            result=restore_files_detached(
                snapshot=backup,installed=installed,
                expected_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
                expected_new_hashes={"rag/new.py":hashlib.sha256(b"candidate").hexdigest()},
                preimage=root/"preimage",preimage_sha256="a"*64,
                journal_path=journal,journal=RollbackJournal.resume(journal),
                external=True,execute=True,
                gate=lambda **kw:{"state":"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY"},
                stopped_probe=lambda *a:{"state":"POSTSTOP_OBSERVED_ONLY",
                                         "observed_stopped":True})
            self.assertEqual(result["state"],"DETACHED_FILES_RESTORED_SHELL_PENDING")
            self.assertEqual(old.read_bytes(),b"original")
            self.assertFalse(new.exists())
            with self.assertRaises(ValueError):
                RollbackJournal.resume(journal)


if __name__=="__main__":
    unittest.main()
