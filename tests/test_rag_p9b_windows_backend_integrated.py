import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_windows_restore_backend import restore_shell
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_rollback_journal import RollbackJournal, read_journal
from test_rag_p9b_winreg_adapter import FakeWinreg


class IntegratedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.desktop=root/"desktop"
        self.desktop.mkdir()
        self.appdata=root/"appdata"
        self.menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        self.link=self.menu/"CodeBridge.lnk"
        self.link.write_bytes(b"snapshot-link")
        self.snapshot=root/"shell.zip"
        self.registry=ScopedHKCU(FakeWinreg())
        snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.snapshot,registry_values=lambda k,n:{"exists":False,"values":{}})
        self.journal_path=root/"journal.jsonl"

    def execute(self):
        return restore_shell(snapshot=self.snapshot,expected_sha256=hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),appdata=self.appdata,
            desktop=self.desktop,registry=self.registry,
            stopped=True,external=True,execute=True,
            journal=RollbackJournal(self.journal_path))

    def test_fake_winreg_and_real_bytes_integrated(self):
        self.link.write_bytes(b"changed-link")
        r=self.execute()
        self.assertEqual(r["state"],"SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED")
        self.assertFalse(r["verified"])
        self.assertEqual(self.link.read_bytes(),b"snapshot-link")
        self.assertEqual(read_journal(self.journal_path)["count"],2)

    def test_journal_reuse_rejected_before_mutation(self):
        self.link.write_bytes(b"changed-link")
        RollbackJournal(self.journal_path)
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(self.link.read_bytes(),b"changed-link")


if __name__=="__main__":
    unittest.main()
