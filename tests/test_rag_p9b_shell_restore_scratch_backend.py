import hashlib
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_restore_executor import execute_shell_restore
from installer.rag_p9b_shell_restore_scratch_backend import ScratchShellBackend


class ScratchTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.appdata=self.root/"appdata"
        self.desktop=self.root/"desktop"
        self.appdata.mkdir()
        self.desktop.mkdir()
        menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        menu.mkdir(parents=True)
        (menu/"CodeBridge.lnk").write_bytes(b"lnk-test")
        self.backup=self.root/"backup.zip"
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.backup,registry_values=lambda k,n:{"exists":True,"values":{}})
        self.digest=hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.backend=ScratchShellBackend(self.root/"scratch")

    def run_executor(self,postverify=None):
        return execute_shell_restore(self.backup,appdata=self.appdata,
            desktop=self.desktop,expected_sha256=self.digest,
            stopped_verified=True,independent=True,execute=True,
            journal=lambda *args:None,
            backend=self.backend.apply,
            postverify=postverify or self.backend.verify)

    def test_recovery_with_independent_postverification(self):
        r=self.run_executor()
        self.assertEqual(r["state"],"SHELL_RESTORE_VERIFIED")
        self.assertFalse(r["registry_modified"])
        self.assertEqual((self.root/"scratch"/"shortcut_0.bin").read_bytes(),b"lnk-test")
        self.assertEqual((self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/"CodeBridge.lnk").read_bytes(),b"lnk-test")

    def test_postverification_denied(self):
        r=self.run_executor(postverify=lambda *args:{"verified":False})
        self.assertEqual(r["state"],"SHELL_RESTORE_REVIEW_REQUIRED")
        self.assertFalse(r["restored"])


if __name__=="__main__":
    unittest.main()
