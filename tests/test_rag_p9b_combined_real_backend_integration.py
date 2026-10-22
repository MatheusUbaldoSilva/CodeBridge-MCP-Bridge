"""Combined lab recovers files and exercises actual shell backend+winreg API facade."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
from installer.rag_p9b_file_restore_executor_lab import restore_files_in_lab
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_crash_preimage import create_crash_preimage
from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_windows_shell_scope import APP_KEYS
from test_rag_p9b_winreg_adapter import FakeWinreg


class CombinedRealBackendTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.installed=self.root/"installed-reference"
        self.installed.mkdir()
        self.lab=self.root/"disposable"
        self.lab.mkdir()
        (self.lab/"pkg").mkdir()
        (self.lab/"pkg"/"old.py").write_bytes(b"partial-update")
        (self.lab/"pkg"/"new.py").write_bytes(b"P9B_LAB_INSTALLER_CREATED_V1")
        self.files_zip=self.root/"files.zip"
        old=b"approved-original"
        with ZipFile(self.files_zip,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "targets":["pkg/old.py","pkg/new.py"],
                "existing":{"pkg/old.py":{"sha256":hashlib.sha256(old).hexdigest()}}}))
            z.writestr("old/pkg/old.py",old)
        self.file_sha=hashlib.sha256(self.files_zip.read_bytes()).hexdigest()
        self.appdata=self.lab/"roaming"
        self.desktop=self.lab/"desktop"
        self.desktop.mkdir()
        menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        menu.mkdir(parents=True)
        self.link=menu/"CodeBridge.lnk"
        self.link.write_bytes(b"original-shortcut")
        self.reg=ScopedHKCU(FakeWinreg())
        self.shell_zip=self.root/"shell.zip"
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.shell_zip,registry_values=lambda key,names:self.reg.read_key(key))
        self.shell_sha=hashlib.sha256(self.shell_zip.read_bytes()).hexdigest()
        self.preimage=self.root/"preimage.zip"
        pre=create_crash_preimage(appdata=self.appdata,desktop=self.desktop,
                                  registry=self.reg,output=self.preimage)
        self.assertTrue(pre["created"])
        self.pre_sha=pre["sha256"]
        self.link.write_bytes(b"broken-new-shortcut")
        self.reg.replace_key(APP_KEYS[0],{"exists":True,"values":{}})
        self.journal_path=self.root/"combined.jsonl"
        self.journal=RollbackJournal(self.journal_path)

    def file_worker(self):
        return restore_files_in_lab(snapshot=self.files_zip,installed=self.installed,
            lab_root=self.lab,expected_sha256=self.file_sha,
            snapshot_probe=lambda *_:{"verified":True})

    def shell_worker(self):
        backend=restore_shell(snapshot=self.shell_zip,expected_sha256=self.shell_sha,
            appdata=self.appdata,desktop=self.desktop,registry=self.reg,
            installed=self.installed,stopped=True,external=True,execute=True,
            journal=self.journal,process_guard=lambda *_:{"state":"NO_RUNNING_CODEBRIDGE"},
            preimage=self.preimage,preimage_sha256=self.pre_sha)
        if backend.get("state")!="SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED":
            return {"state":"SHELL_BACKEND_UNVERIFIED","verified":False}
        check=verify_restored_shell(self.shell_zip,appdata=self.appdata,desktop=self.desktop,
                                  registry_values=lambda key,names:self.reg.read_key(key))
        return {"state":"SHELL_LAB_VERIFIED" if check.get("verified") else "SHELL_POSTVERIFY_FAILED",
                "verified":check.get("verified"),"shortcuts":check.get("shortcuts_checked"),
                "registry_keys":check.get("registry_keys_checked")}

    def postverify(self):
        shell=verify_restored_shell(self.shell_zip,appdata=self.appdata,
            desktop=self.desktop,registry_values=lambda key,names:self.reg.read_key(key))
        files=((self.lab/"pkg"/"old.py").read_bytes()==b"approved-original"
            and not (self.lab/"pkg"/"new.py").exists())
        return {"verified":files and shell.get("verified") is True}

    def test_full_backend_combined_with_durable_journal(self):
        r=recover_combined_lab(file_worker=self.file_worker,
          shell_worker=self.shell_worker,verify_worker=self.postverify,
          journal=self.journal,independent=True,
          lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertTrue(r["verified"])
        self.assertEqual((r["files"],r["new_targets"],r["shortcuts"],r["fake_registry_keys"]),(1,1,5,2))
        # Four coordinator and two actual backend journal events.
        self.assertEqual(read_journal(self.journal_path)["count"],6)

    def test_foreign_new_file_stops_before_shell_backend(self):
        (self.lab/"pkg"/"new.py").write_bytes(b"foreign-data")
        r=recover_combined_lab(file_worker=self.file_worker,
          shell_worker=self.shell_worker,verify_worker=self.postverify,
          journal=self.journal,independent=True,
          lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["reason"],"FILE_RESTORE_NOT_VERIFIED")
        self.assertEqual(self.link.read_bytes(),b"broken-new-shortcut")
        self.assertEqual(read_journal(self.journal_path)["count"],2)


if __name__=="__main__":
    unittest.main()
