import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_postverify import verify_restored_shell


class PostverifyTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.appdata=self.root/"appdata"
        self.desktop=self.root/"desktop"
        self.appdata.mkdir()
        self.desktop.mkdir()
        self.menu=self.appdata/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        (self.menu/"CodeBridge.lnk").write_bytes(b"old")
        self.zip=self.root/"backup.zip"
        self.registry=lambda k,n:{"exists":True,"values":{}}
        r=snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
                               snapshot=self.zip,registry_values=self.registry)
        self.assertTrue(r["created"])

    def verify(self,registry=None):
        return verify_restored_shell(self.zip,appdata=self.appdata,
                                    desktop=self.desktop,
                                    registry_values=registry or self.registry)

    def test_baseline_matches(self):
        self.assertEqual(self.verify()["state"],"SHELL_POSTRESTORE_MATCHED")

    def test_link_changed(self):
        (self.menu/"CodeBridge.lnk").write_bytes(b"changed")
        self.assertEqual(self.verify()["reason"],"SHORTCUT_BYTES_MISMATCH")

    def test_link_removed(self):
        (self.menu/"CodeBridge.lnk").unlink()
        self.assertEqual(self.verify()["reason"],"SHORTCUT_EXISTENCE_MISMATCH")

    def test_rejects_symlinked_parent(self):
        actual=self.menu.with_name("real-menu")
        self.menu.rename(actual)
        try:
            self.menu.symlink_to(actual,target_is_directory=True)
        except OSError:
            actual.rename(self.menu)
            self.skipTest("directory symlinks disabled")
        self.assertEqual(self.verify()["reason"],"SHORTCUT_PATH_CHANGED")

    def test_registry_changed(self):
        self.assertEqual(self.verify(registry=lambda k,n:{"exists":False,"values":{}})["reason"],
                         "REGISTRY_BASELINE_MISMATCH")


if __name__=="__main__":
    unittest.main()
