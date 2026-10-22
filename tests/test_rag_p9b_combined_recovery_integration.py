"""Integration of real lab file rollback + actual fake-shell restoration."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
from installer.rag_p9b_file_restore_executor_lab import restore_files_in_lab
from installer.rag_p9b_crash_preimage import create_crash_preimage, verify_crash_preimage
from installer.rag_p9b_windows_shell_scope import MENU_LINKS, DESKTOP_LINK


class FakeRegistry:
    def read_key(self, key):
        return {"exists": True, "values": {}}


class CombinedIntegration(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.lab=self.root/"lab"
        self.lab.mkdir()
        (self.lab/"pkg").mkdir()
        (self.lab/"pkg"/"old.py").write_bytes(b"changed-by-failed-installer")
        (self.lab/"pkg"/"new.py").write_bytes(b"P9B_LAB_INSTALLER_CREATED_V1")
        self.install=self.root/"real-install-not-touched"
        self.install.mkdir()
        self.snapshot=self.root/"file-snapshot.zip"
        old=b"known-old"
        with ZipFile(self.snapshot,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "targets":["pkg/old.py","pkg/new.py"],
                "existing":{"pkg/old.py":{"sha256":hashlib.sha256(old).hexdigest()}}}))
            z.writestr("old/pkg/old.py",old)
        self.sha=hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.desktop=self.lab/"desktop"
        self.desktop.mkdir()
        self.roaming=self.lab/"roaming"
        self.menu=self.roaming/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        self.shell=[self.menu/n for n in MENU_LINKS]+[self.desktop/DESKTOP_LINK]
        for i,path in enumerate(self.shell):
            path.write_bytes(("known-shortcut-"+str(i)).encode())
        self.shellzip=self.root/"shell-original.zip"
        saved=create_crash_preimage(appdata=self.roaming,desktop=self.desktop,
                                    registry=FakeRegistry(),output=self.shellzip)
        self.assertTrue(saved["created"])
        self.shellsha=saved["sha256"]
        self.shell[0].write_bytes(b"interrupted-shortcut")
        self.fake_registry=self.lab/"fake-registry.json"
        self.fake_registry.write_text('{"partial":true}',encoding="utf-8")
        self.logs=[]

    def restore_files(self):
        return restore_files_in_lab(
            snapshot=self.snapshot, installed=self.install,
            lab_root=self.lab, expected_sha256=self.sha,
            snapshot_probe=lambda *_:{"verified":True})

    def restore_shell(self):
        if not verify_crash_preimage(self.shellzip,self.shellsha)["verified"]:
            return {"state":"SHELL_UNVERIFIED","verified":False}
        with ZipFile(self.shellzip) as z:
            manifest=json.loads(z.read("manifest.json"))
            for i,item in enumerate(manifest["links"]):
                if item["exists"]:
                    self.shell[i].write_bytes(z.read(f"links/{i}.bin"))
                else:
                    self.shell[i].unlink(missing_ok=True)
            self.fake_registry.write_text(json.dumps(manifest["registry"],sort_keys=True),encoding="utf-8")
        return {"state":"SHELL_LAB_VERIFIED","verified":True,
                "shortcuts":len(self.shell),"registry_keys":len(manifest["registry"])}

    def verify_all(self):
        return {"verified":(
            (self.lab/"pkg"/"old.py").read_bytes()==b"known-old"
            and not (self.lab/"pkg"/"new.py").exists()
            and self.shell[0].read_bytes()==b"known-shortcut-0"
            and len(json.loads(self.fake_registry.read_text(encoding="utf-8")))==2)}

    def test_real_file_and_fake_shell_in_one_journal(self):
        from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
        journal_path=self.root/"journal.jsonl"
        journal=RollbackJournal(journal_path)
        result=recover_combined_lab(
            file_worker=self.restore_files,shell_worker=self.restore_shell,
            verify_worker=self.verify_all,journal=journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(result["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertTrue(result["verified"])
        self.assertEqual(result["files"],1)
        self.assertEqual(result["new_targets"],1)
        self.assertEqual((result["shortcuts"],result["fake_registry_keys"]),(5,2))
        self.assertEqual(read_journal(journal_path)["count"],4)

    def test_unrecognized_target_blocks_shell_restore(self):
        (self.lab/"pkg"/"new.py").write_bytes(b"not-owned-by-installer")
        result=recover_combined_lab(
            file_worker=self.restore_files,shell_worker=self.restore_shell,
            verify_worker=self.verify_all,journal=lambda *args:self.logs.append(args),
            independent=True,lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(result["reason"],"FILE_RESTORE_NOT_VERIFIED")
        self.assertEqual(self.shell[0].read_bytes(),b"interrupted-shortcut")


if __name__=="__main__":
    unittest.main()
