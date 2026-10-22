import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_restore_scratch import rehearse_shell_restore_scratch


class RestoreTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.roaming=self.root/"roaming"
        self.desktop=self.root/"desktop"
        self.roaming.mkdir()
        self.desktop.mkdir()
        menu=self.roaming/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        menu.mkdir(parents=True)
        (menu/"CodeBridge.lnk").write_bytes(b"pretend link")
        self.zip=self.root/"shell.zip"
        self.scratch=self.root/"scratch"
        created=snapshot_shell_state(appdata=self.roaming,desktop=self.desktop,
            snapshot=self.zip,registry_values=lambda k,n:{"exists":True,"values":{}})
        self.assertTrue(created["created"])

    def test_scratch_rehearsed_without_real_restore(self):
        r=rehearse_shell_restore_scratch(self.zip,self.scratch)
        self.assertEqual(r["state"],"SHELL_SCRATCH_RESTORE_REHEARSED")
        self.assertFalse(r["registry_modified"])
        self.assertEqual((self.scratch/"shortcut_0.bin").read_bytes(),b"pretend link")

    def test_existing_scratch_refused(self):
        self.scratch.mkdir()
        r=rehearse_shell_restore_scratch(self.zip,self.scratch)
        self.assertEqual(r["reason"],"SCRATCH_PATH_UNSAFE")


if __name__=="__main__":
    unittest.main()
