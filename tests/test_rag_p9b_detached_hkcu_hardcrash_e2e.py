"""Hard-exit during shell registry restore with file-persisted FakeHKCU.

Registry is simulated by JSON in TemporaryDirectory, never Windows HKCU.
The real production shell restore backend is exercised in both subprocesses.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
from installer.rag_p9b_windows_shell_scope import APP_KEYS


class DetachedHKCUHardCrashTests(unittest.TestCase):
    def test_backend_hard_exit_mid_registry_then_fresh_process_replay(self):
        from test_rag_p9b_detached_combined_backend_e2e import DetachedBackendE2ETests
        fixture=DetachedBackendE2ETests(
            "test_full_detached_backends_on_isolated_files_and_fake_hkcu")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fake_registry=fixture.root/"fake-hkcu.json"
        fake_registry.write_text(json.dumps({
            key:{"exists":True,"values":{}} for key in APP_KEYS
        }),encoding="utf-8")
        fixture.journal("SHELL_DETACHED_COMBINED_ARMED",
                        {"transaction_sha256":"a"*64})
        worker=fixture.root/"registry_worker.py"
        worker.write_text("""
import hashlib,json,os,sys
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_shell_postverify import verify_restored_shell
root=Path(sys.argv[1])
state_file=root/"fake-hkcu.json"
class PersistedFakeRegistry:
    def read_key(self,key):
        data=json.loads(state_file.read_text(encoding="utf-8"))
        return data.get(key,{"exists":False,"values":{}})
    def replace_key(self,key,record):
        data=json.loads(state_file.read_text(encoding="utf-8"))
        data[key]=record
        temp=state_file.with_suffix(".pending")
        with temp.open("w",encoding="utf-8") as f:
            json.dump(data,f,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,state_file)
        if sys.argv[2]=="crash":
            os._exit(80)
registry=PersistedFakeRegistry()
snapshot=root/"shell.zip"
pre=root/"preimage.zip"
journal=RollbackJournal.resume(root/"combined.jsonl",
    expected_transaction_sha256="a"*64)
result=restore_shell(snapshot=snapshot,
    expected_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
    appdata=root/"roaming",desktop=root/"desktop",registry=registry,
    installed=root/"installed",stopped=True,external=True,execute=True,
    journal=journal,
    process_guard=lambda *a:{"state":"NO_RUNNING_CODEBRIDGE"},
    preimage=pre,
    preimage_sha256=hashlib.sha256(pre.read_bytes()).hexdigest())
if result.get("state")!="SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED":
    sys.exit(4)
verified=verify_restored_shell(snapshot,appdata=root/"roaming",
    desktop=root/"desktop",
    registry_values=lambda key,names:registry.read_key(key))
if not verified.get("verified"):sys.exit(5)
""",encoding="utf-8")
        repo=Path(__file__).resolve().parents[1]
        env=dict(os.environ)
        env["PYTHONPATH"]=str(repo/"tests")+os.pathsep+str(repo)+os.pathsep+env.get("PYTHONPATH","")
        first=subprocess.run([sys.executable,str(worker),str(fixture.root),"crash"],
            cwd=repo,env=env,capture_output=True,timeout=15)
        self.assertEqual(first.returncode,80,first.stderr)
        interim=json.loads(fake_registry.read_text(encoding="utf-8"))
        self.assertFalse(interim[APP_KEYS[0]]["exists"])
        self.assertTrue(interim[APP_KEYS[1]]["exists"])
        self.assertEqual(fixture.shortcut.read_bytes(),b"original")
        self.assertEqual(read_journal(fixture.journal_path)["last_state"],
                         "SHELL_BACKEND_ARMED")
        second=subprocess.run([sys.executable,str(worker),str(fixture.root),"replay"],
            cwd=repo,env=env,capture_output=True,timeout=15)
        self.assertEqual(second.returncode,0,second.stderr)
        final=json.loads(fake_registry.read_text(encoding="utf-8"))
        self.assertFalse(final[APP_KEYS[0]]["exists"])
        self.assertFalse(final[APP_KEYS[1]]["exists"])
        self.assertEqual(fixture.shortcut.read_bytes(),b"original")
        self.assertEqual(read_journal(fixture.journal_path)["last_state"],
                         "SHELL_BACKEND_WRITTEN")
        self.assertNotIn("SHELL_DETACHED_COMBINED_VERIFIED",
                         fixture.journal_path.read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
