"""Full detached coordinator exercises real file and shell backends in a fixture."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_detached_combined_recovery import recover_detached_combined
from installer.rag_p9b_detached_file_rollback_executor import restore_files_detached
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_crash_preimage import create_crash_preimage
from installer.rag_p9b_rollback_journal import RollbackJournal
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from test_rag_p9b_winreg_adapter import FakeWinreg


class DetachedBackendE2ETests(unittest.TestCase):
    def setUp(self):
        ctx=tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.root=Path(ctx.name)
        self.installed=self.root/"installed"
        (self.installed/"rag").mkdir(parents=True)
        self.old=self.installed/"rag"/"old.py"
        self.new=self.installed/"rag"/"new.py"
        self.old.write_bytes(b"updated")
        self.new.write_bytes(b"new-candidate")
        self.backup=self.root/"files.zip"
        with ZipFile(self.backup,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "installed_root":str(self.installed),
                "targets":["rag/old.py","rag/new.py"],
                "existing":{"rag/old.py":{
                    "sha256":hashlib.sha256(b"original").hexdigest()}}}))
            z.writestr("old/rag/old.py",b"original")
        self.backup_sha=hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.appdata=self.root/"roaming"
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()
        menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        menu.mkdir(parents=True)
        self.shortcut=menu/"CodeBridge.lnk"
        self.shortcut.write_bytes(b"original")
        self.registry=ScopedHKCU(FakeWinreg())
        self.shell_zip=self.root/"shell.zip"
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.shell_zip,
            registry_values=lambda key,names:self.registry.read_key(key))
        self.shell_sha=hashlib.sha256(self.shell_zip.read_bytes()).hexdigest()
        self.preimage=self.root/"preimage.zip"
        pre=create_crash_preimage(appdata=self.appdata,desktop=self.desktop,
            registry=self.registry,output=self.preimage)
        assert pre["created"]
        self.pre_sha=pre["sha256"]
        self.shortcut.write_bytes(b"updated-shortcut")
        self.journal_path=self.root/"combined.jsonl"
        self.journal=RollbackJournal(self.journal_path)

    def files(self):
        return restore_files_detached(
            snapshot=self.backup,installed=self.installed,
            expected_sha256=self.backup_sha,
            expected_new_hashes={"rag/new.py":hashlib.sha256(b"new-candidate").hexdigest()},
            preimage=self.preimage,preimage_sha256=self.pre_sha,
            journal_path=self.journal_path,journal=self.journal,
            external=True,execute=True,
            gate=lambda **kw:{"state":"PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY"},
            stopped_probe=lambda *_:{"state":"POSTSTOP_OBSERVED_ONLY",
                                     "observed_stopped":True})

    def shell(self):
        result=restore_shell(
            snapshot=self.shell_zip,expected_sha256=self.shell_sha,
            appdata=self.appdata,desktop=self.desktop,registry=self.registry,
            installed=self.installed,stopped=True,external=True,execute=True,
            journal=self.journal,
            process_guard=lambda *_:{"state":"NO_RUNNING_CODEBRIDGE"},
            preimage=self.preimage,preimage_sha256=self.pre_sha)
        if result["state"]!="SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED":
            return {"state":"SHELL_RESTORE_REVIEW_REQUIRED","restored":False}
        verified=verify_restored_shell(
            self.shell_zip,appdata=self.appdata,desktop=self.desktop,
            registry_values=lambda key,names:self.registry.read_key(key))
        return {"state":"SHELL_RESTORE_VERIFIED" if verified["verified"]
                else "SHELL_RESTORE_REVIEW_REQUIRED",
                "restored":verified["verified"]}

    def verify(self):
        shell=verify_restored_shell(self.shell_zip,
            appdata=self.appdata,desktop=self.desktop,
            registry_values=lambda key,names:self.registry.read_key(key))
        return {"verified":(self.old.read_bytes()==b"original"
                            and not self.new.exists()
                            and shell["verified"] is True)}

    def test_full_detached_backends_on_isolated_files_and_fake_hkcu(self):
        result=recover_detached_combined(
            file_worker=self.files,shell_worker=self.shell,
            verify_worker=self.verify,journal=self.journal,
            independent=True,execute=True)
        self.assertEqual(result["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
        self.assertTrue(result["verified"])
        self.assertFalse(result["cutover_authorized"])
        self.assertEqual(self.shortcut.read_bytes(),b"original")

    def test_restore_replay_after_shell_failure_with_actual_fixture_backends(self):
        calls=[]
        def fail_before_shell():
            calls.append("interrupted")
            raise OSError("simulated shell crash")
        first=recover_detached_combined(
            file_worker=self.files,shell_worker=fail_before_shell,
            verify_worker=self.verify,journal=self.journal,
            independent=True,execute=True)
        self.assertEqual(first["state"],"DETACHED_COMBINED_REVIEW_REQUIRED")
        self.assertEqual(first["failed_stage"],"SHELL")
        self.assertEqual(calls,["interrupted"])
        self.assertEqual(self.old.read_bytes(),b"original")
        self.assertFalse(self.new.exists())
        self.assertEqual(self.shortcut.read_bytes(),b"updated-shortcut")
        # Restart from the persisted journal. The file worker is idempotent:
        # no new installer files remain and old contents already match.
        self.journal=RollbackJournal.resume(self.journal_path)
        second=recover_detached_combined(
            file_worker=self.files,shell_worker=self.shell,
            verify_worker=self.verify,journal=self.journal,
            independent=True,execute=True)
        self.assertEqual(second["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
        self.assertTrue(second["verified"])
        self.assertEqual(self.shortcut.read_bytes(),b"original")
        with self.assertRaises(ValueError):
            RollbackJournal.resume(self.journal_path)

    def test_foreign_new_file_blocks_shell_backend(self):
        self.new.write_bytes(b"foreign")
        result=recover_detached_combined(
            file_worker=self.files,shell_worker=self.shell,
            verify_worker=self.verify,journal=self.journal,
            independent=True,execute=True)
        self.assertEqual(result["reason"],"FILES_NOT_VERIFIED")
        self.assertEqual(self.shortcut.read_bytes(),b"updated-shortcut")


if __name__=="__main__":
    unittest.main()
