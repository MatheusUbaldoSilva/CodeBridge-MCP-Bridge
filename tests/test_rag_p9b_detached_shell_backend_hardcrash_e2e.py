"""Crash real shell backend within isolated fixture; HKCU is FakeWinreg."""
import hashlib
import os
import subprocess
import sys
import unittest
from pathlib import Path

from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
from installer.rag_p9b_shell_postverify import verify_restored_shell


class DetachedShellBackendHardCrashTests(unittest.TestCase):
    def test_shell_worker_os_exit_then_new_process_resume(self):
        from test_rag_p9b_detached_combined_backend_e2e import DetachedBackendE2ETests
        fixture=DetachedBackendE2ETests(
            "test_full_detached_backends_on_isolated_files_and_fake_hkcu")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.journal("SHELL_DETACHED_COMBINED_ARMED",
                        {"transaction_sha256":"a"*64})
        repo=Path(__file__).resolve().parents[1]
        worker=fixture.root/"shell_worker.py"
        worker.write_text("""
import hashlib,os,sys
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_windows_restore_backend import restore_shell
import installer.rag_p9b_windows_restore_backend as backend
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from test_rag_p9b_winreg_adapter import FakeWinreg
root=Path(sys.argv[1])
journal=RollbackJournal.resume(root/"combined.jsonl",
    expected_transaction_sha256="a"*64)
snapshot=root/"shell.zip"; pre=root/"preimage.zip"
if sys.argv[2]=="crash":
    original=backend.write_atomic_shortcut
    def crash_after_replace(target,data):
        original(target,data)
        os._exit(79)
    backend.write_atomic_shortcut=crash_after_replace
result=restore_shell(
    snapshot=snapshot,
    expected_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
    appdata=root/"roaming",desktop=root/"desktop",
    registry=ScopedHKCU(FakeWinreg()),
    installed=root/"installed",
    stopped=True,external=True,execute=True,journal=journal,
    process_guard=lambda *a:{"state":"NO_RUNNING_CODEBRIDGE"},
    preimage=pre,
    preimage_sha256=hashlib.sha256(pre.read_bytes()).hexdigest())
if result.get("state")!="SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED":
    sys.exit(4)
""",encoding="utf-8")
        env=dict(os.environ)
        env["PYTHONPATH"]=str(repo/"tests")+os.pathsep+str(repo)+os.pathsep+env.get("PYTHONPATH","")
        first=subprocess.run([sys.executable,str(worker),str(fixture.root),"crash"],
            cwd=repo,env=env,capture_output=True,timeout=15)
        self.assertEqual(first.returncode,79,first.stderr)
        self.assertEqual(fixture.shortcut.read_bytes(),b"original")
        self.assertEqual(read_journal(fixture.journal_path)["last_state"],
                         "SHELL_BACKEND_ARMED")
        second=subprocess.run([sys.executable,str(worker),str(fixture.root),"replay"],
            cwd=repo,env=env,capture_output=True,timeout=15)
        self.assertEqual(second.returncode,0,second.stderr)
        result=verify_restored_shell(
            fixture.shell_zip,appdata=fixture.appdata,desktop=fixture.desktop,
            registry_values=lambda key,names:fixture.registry.read_key(key))
        self.assertTrue(result["verified"])
        self.assertEqual(read_journal(fixture.journal_path)["last_state"],
                         "SHELL_BACKEND_WRITTEN")
        self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED",
                         fixture.journal_path.read_text(encoding="utf-8"))


if __name__=="__main__":unittest.main()
