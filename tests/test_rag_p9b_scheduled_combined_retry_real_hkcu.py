"""Real isolated Windows registry/file combined recovery through bounded adapter."""
import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

from installer.rag_p9b_scheduled_combined_retry_adapter import run_lab_retry
from installer.rag_p9b_detached_combined_recovery_lab import execute
from installer.rag_p9b_shell_postverify import verify_restored_shell
from test_rag_p9b_full_scope_actual_hkcu_integration import FullScopeActualHKCUTests


@unittest.skipUnless(sys.platform=="win32", "actual scoped HKCU lab needs Windows")
class ScheduledAdapterRealHKCUTests(unittest.TestCase):
    def setUp(self):
        self.fixture=FullScopeActualHKCUTests("test_isolated_real_hkcu_and_files_combined")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def test_real_combined_rollback_and_terminal(self):
        f=self.fixture
        config=f.lab.parent/"bounded-combined-config.json"
        journal=f.lab.parent/"bounded-combined-journal.jsonl"
        retry=f.lab.parent/"bounded-combined-retry.json"
        with ZipFile(f.files_zip) as archive:
            source_root=json.loads(archive.read("manifest.json"))["installed_root"]
        copied_snapshot=f.lab.parent/"isolated-files-snapshot.zip"
        shutil.copyfile(f.files_zip,copied_snapshot)
        self.assertEqual(hashlib.sha256(copied_snapshot.read_bytes()).hexdigest(),f.file_sha)
        config.write_text(json.dumps({
            "lab":str(f.lab), "appdata":str(f.appdata), "desktop":str(f.desktop),
            "token":f.token, "installed":source_root,
            "snapshot":str(copied_snapshot), "snapshot_sha256":f.file_sha,
            "shell_snapshot":str(f.shell_zip), "shell_snapshot_sha256":f.shell_sha,
            "preimage":str(f.preimage), "preimage_sha256":f.pre_sha,
            "journal":str(journal)}),encoding="utf-8")
        signature=hashlib.sha256(config.read_bytes()).hexdigest()
        invoked=[]
        def worker(path):
            report=execute(path)
            invoked.append(report)
            return report
        result=run_lab_retry(config=config,retry_ledger=retry,
                             transaction_sha256=signature,
                             temp_root=f.lab.parent,worker=worker)
        self.assertTrue(result["verified"],result)
        self.assertEqual(result["state"],"P9B_LAB_COMBINED_TERMINAL_PERSISTED")
        report=invoked[0]
        self.assertEqual(report["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertEqual((report["files"],report["new_targets"],
                          report["shortcuts"],report["fake_registry_keys"]),
                         (236,22,5,2))
        self.assertTrue(verify_restored_shell(
            f.shell_zip,appdata=f.appdata,desktop=f.desktop,
            registry_values=lambda key,names:f.reg.read_key(key))["verified"])
        self.assertEqual(json.loads(retry.read_text())["state"],"TERMINAL")
        again=run_lab_retry(config=config,retry_ledger=retry,
                             transaction_sha256=signature,
                             temp_root=f.lab.parent,worker=worker)
        self.assertFalse(again["verified"])
        self.assertEqual(again["reason"],"DURABLE_TERMINAL_STATE")
        self.assertEqual(len(invoked),1)


if __name__=="__main__":
    unittest.main()