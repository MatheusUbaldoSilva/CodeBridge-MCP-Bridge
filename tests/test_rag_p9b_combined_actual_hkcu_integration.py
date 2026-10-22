"""Combined real file and shortcut backend with actual isolated HKCU API.

Production registry paths are never opened: ScopedHKCU uses unique remap.
"""
import hashlib
import sys
import unittest
from pathlib import Path

from test_rag_p9b_combined_real_backend_integration import CombinedRealBackendTests
from test_rag_p9b_real_hkcu_isolated import RealHKCUIsolatedTests
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_crash_preimage import create_crash_preimage
from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_rollback_journal import read_journal
from installer.rag_p9b_windows_shell_scope import APP_KEYS


@unittest.skipUnless(sys.platform=="win32","real HKCU requires Windows")
class CombinedActualHKCUTests(unittest.TestCase):
    file_worker=CombinedRealBackendTests.file_worker
    shell_worker=CombinedRealBackendTests.shell_worker
    postverify=CombinedRealBackendTests.postverify
    def setUp(self):
        CombinedRealBackendTests.setUp(self)
        RealHKCUIsolatedTests.setUp(self)
        self.reg=self.adapter
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.shell_zip,
            registry_values=lambda key,names:self.reg.read_key(key))
        self.shell_sha=hashlib.sha256(self.shell_zip.read_bytes()).hexdigest()
        self.preimage.unlink()
        pre=create_crash_preimage(appdata=self.appdata,desktop=self.desktop,
                                   registry=self.reg,output=self.preimage)
        self.assertTrue(pre["created"])
        self.pre_sha=pre["sha256"]
        self.reg.replace_key(APP_KEYS[0],{"exists":True,"values":{}})

    def tearDown(self):
        RealHKCUIsolatedTests.tearDown(self)

    def test_isolated_real_hkcu_and_files_combined(self):
        r=recover_combined_lab(file_worker=self.file_worker,shell_worker=self.shell_worker,
            verify_worker=self.postverify,journal=self.journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertTrue(r["verified"])
        self.assertEqual(r["fake_registry_keys"],2)
        self.assertEqual(read_journal(self.journal_path)["count"],6)
        for key in APP_KEYS:
            self.assertEqual(self.reg.read_key(key),{"exists":False,"values":{}})
    def test_foreign_file_refuses_before_real_hkcu(self):
        (self.lab/"pkg"/"new.py").write_bytes(b"foreign")
        r=recover_combined_lab(file_worker=self.file_worker,shell_worker=self.shell_worker,
            verify_worker=self.postverify,journal=self.journal,independent=True,
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"})
        self.assertEqual(r["reason"],"FILE_RESTORE_NOT_VERIFIED")
        self.assertTrue(self.reg.read_key(APP_KEYS[0])["exists"])
