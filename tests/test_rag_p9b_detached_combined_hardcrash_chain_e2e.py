"""Combined file + shell rollback across two external workers and hard crash.

Uses isolated fixture paths and persisted fake HKCU only. Never touches real
installation, native Windows HKCU, NSIS, or installed CodeBridge processes.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from installer.rag_p9b_rollback_journal import read_journal
from installer.rag_p9b_windows_shell_scope import APP_KEYS


class CombinedHardCrashChainTests(unittest.TestCase):
    def test_first_worker_crashes_mid_hkcu_second_completes_both_backends(self):
        from test_rag_p9b_detached_combined_backend_e2e import DetachedBackendE2ETests
        fixture=DetachedBackendE2ETests(
            "test_full_detached_backends_on_isolated_files_and_fake_hkcu")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        tx=fixture.root/"external-combined.jsonl"
        hkcu=fixture.root/"fake-hkcu.json"
        hkcu.write_text(json.dumps({
            key:{"exists":True,"values":{}} for key in APP_KEYS
        }),encoding="utf-8")
        worker=fixture.root/"combined_worker.py"
        worker.write_text("""
import hashlib,json,os,sys
from pathlib import Path
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_detached_combined_recovery import recover_detached_combined
from installer.rag_p9b_detached_file_rollback_executor import restore_files_detached
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_shell_postverify import verify_restored_shell
root=Path(sys.argv[1]);mode=sys.argv[2]
tx=root/"external-combined.jsonl"
journal=(RollbackJournal(tx) if mode=="crash" else
         RollbackJournal.resume(tx))
backup=root/"files.zip";shell=root/"shell.zip";pre=root/"preimage.zip"
installed=root/"installed";state_file=root/"fake-hkcu.json"
class FakePersistentHKCU:
    def read_key(self,key):
        return json.loads(state_file.read_text(encoding="utf-8")).get(
            key,{"exists":False,"values":{}})
    def replace_key(self,key,record):
        data=json.loads(state_file.read_text(encoding="utf-8"))
        data[key]=record
        tmp=state_file.with_suffix(".pending")
        with tmp.open("w",encoding="utf-8") as stream:
            json.dump(data,stream,sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,state_file)
        if mode=="crash":os._exit(81)
reg=FakePersistentHKCU()
def file_worker():
    return restore_files_detached(
        snapshot=backup,installed=installed,
        expected_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
        expected_new_hashes={
            "rag/new.py":hashlib.sha256(b"new-candidate").hexdigest()},
        preimage=pre,
        preimage_sha256=hashlib.sha256(pre.read_bytes()).hexdigest(),
        journal_path=tx,journal=journal,external=True,execute=True,
        gate=lambda **kw:{
            "state":"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY"},
        stopped_probe=lambda *a:{
            "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
def shell_worker():
    applied=restore_shell(
        snapshot=shell,
        expected_sha256=hashlib.sha256(shell.read_bytes()).hexdigest(),
        appdata=root/"roaming",desktop=root/"desktop",registry=reg,
        installed=installed,stopped=True,external=True,execute=True,
        journal=journal,
        process_guard=lambda *a:{"state":"NO_RUNNING_CODEBRIDGE"},
        preimage=pre,
        preimage_sha256=hashlib.sha256(pre.read_bytes()).hexdigest())
    if applied.get("state")!="SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED":
        return {"state":"SHELL_RESTORE_REVIEW_REQUIRED","restored":False}
    checked=verify_restored_shell(
        shell,appdata=root/"roaming",desktop=root/"desktop",
        registry_values=lambda key,names:reg.read_key(key))
    return {"state":"SHELL_RESTORE_VERIFIED" if checked["verified"]
            else "SHELL_RESTORE_REVIEW_REQUIRED",
            "restored":checked["verified"]}
def final_verify():
    checked=verify_restored_shell(
        shell,appdata=root/"roaming",desktop=root/"desktop",
        registry_values=lambda key,names:reg.read_key(key))
    return {"verified":checked["verified"] and
            (installed/"rag"/"old.py").read_bytes()==b"original" and
            not (installed/"rag"/"new.py").exists()}
result=recover_detached_combined(
    file_worker=file_worker,shell_worker=shell_worker,
    verify_worker=final_verify,journal=journal,
    independent=True,execute=True)
if mode=="replay":
    if result.get("state")!="DETACHED_COMBINED_RESTORE_VERIFIED":
        sys.exit(5)
""",encoding="utf-8")
        repo=Path(__file__).resolve().parents[1]
        env=dict(os.environ)
        env["PYTHONPATH"]=str(repo)+os.pathsep+env.get("PYTHONPATH","")
        def launch(mode):
            return subprocess.run([sys.executable,str(worker),
                                   str(fixture.root),mode],
                    cwd=repo,env=env,capture_output=True,timeout=15)
        first=launch("crash")
        self.assertEqual(first.returncode,81,first.stderr)
        self.assertEqual(fixture.old.read_bytes(),b"original")
        self.assertFalse(fixture.new.exists())
        self.assertEqual(fixture.shortcut.read_bytes(),b"original")
        observed=read_journal(tx)
        self.assertEqual(observed["last_state"],"SHELL_BACKEND_ARMED")
        self.assertTrue(json.loads(hkcu.read_text(encoding="utf-8"))[
            APP_KEYS[1]]["exists"])
        second=launch("replay")
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(fixture.old.read_bytes(),b"original")
        self.assertFalse(fixture.new.exists())
        self.assertEqual(fixture.shortcut.read_bytes(),b"original")
        final=json.loads(hkcu.read_text(encoding="utf-8"))
        self.assertTrue(all(not final[key]["exists"] for key in APP_KEYS))
        self.assertEqual(read_journal(tx)["last_state"],
                         "SHELL_DETACHED_COMBINED_VERIFIED")
        self.assertNotIn("cutover_authorized",tx.read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
