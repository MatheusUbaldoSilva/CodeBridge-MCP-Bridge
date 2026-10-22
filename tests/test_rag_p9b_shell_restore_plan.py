import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_shell_snapshot import snapshot_shell_state
from installer.rag_p9b_shell_restore_plan import build_shell_restore_plan


class ShellRestorePlanTests(unittest.TestCase):
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
        (self.menu/"CodeBridge.lnk").write_bytes(b"link")
        self.snapshot=self.root/"snapshot.zip"
        saved=snapshot_shell_state(appdata=self.appdata,desktop=self.desktop,
            snapshot=self.snapshot,registry_values=lambda key,names:{"exists":True,"values":{}})
        self.assertTrue(saved["created"])
        self.digest=hashlib.sha256(self.snapshot.read_bytes()).hexdigest()

    def run_plan(self,**changes):
        inputs=dict(snapshot=self.snapshot,appdata=self.appdata,desktop=self.desktop,
            expected_snapshot_sha256=self.digest,installed_stopped=True)
        inputs.update(changes)
        return build_shell_restore_plan(**inputs)

    def test_valid_snapshot_only_generates_plan(self):
        r=self.run_plan()
        self.assertEqual(r["state"],"SHELL_RESTORE_PLAN_ONLY")
        self.assertTrue(r["verified"])
        self.assertFalse(r["production_restore_authorized"])
        self.assertEqual(len(r["shortcut_actions"]),5)
        self.assertEqual(len(r["registry_actions"]),2)

    def test_live_installation_blocks(self):
        self.assertEqual(self.run_plan(installed_stopped=False)["reason"],
                         "INSTALLATION_MUST_BE_STOPPED")

    def test_wrong_hash_blocks(self):
        self.assertEqual(self.run_plan(expected_snapshot_sha256="f"*64)["reason"],
                         "SNAPSHOT_HASH_MISMATCH")

    def test_symlink_shortcut_blocks(self):
        target=self.menu/"Atualizar CodeBridge.lnk"
        try:
            target.symlink_to(self.snapshot)
        except OSError:
            self.skipTest("Symlinks not authorized")
        self.assertEqual(self.run_plan()["reason"],"TARGET_PATH_NOT_REGULAR")

    def test_existing_snapshot_not_modified(self):
        before=self.snapshot.read_bytes()
        self.run_plan()
        self.assertEqual(self.snapshot.read_bytes(),before)


if __name__=="__main__":
    unittest.main()
