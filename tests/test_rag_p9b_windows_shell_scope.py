import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_windows_shell_scope import inspect_shell_scope


class ShellScopeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.menu=self.root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"
        self.menu.mkdir(parents=True)
        self.desktop=self.root/"desktop"
        self.desktop.mkdir()

    def scope(self):
        return inspect_shell_scope(
            appdata=self.root/"roaming",desktop=self.desktop,
            registry_query=lambda k:{"exists":False,"value_names":[]})

    def test_empty_scope_only_observed(self):
        r=self.scope()
        self.assertEqual(r["state"],"SHELL_SCOPE_OBSERVED_ONLY")
        self.assertFalse(r["restore_performed"])
        self.assertEqual(len(r["shortcuts"]),5)

    def test_one_existing_shortcut_hashed(self):
        (self.menu/"CodeBridge.lnk").write_bytes(b"binary stub")
        r=self.scope()
        self.assertEqual(r["shortcuts"][0]["bytes"],11)
        self.assertEqual(len(r["shortcuts"][0]["sha256"]),64)

    def test_directory_instead_of_link_blocks(self):
        (self.menu/"CodeBridge.lnk").mkdir()
        self.assertEqual(self.scope()["reason"],"UNEXPECTED_SHELL_TARGET")


if __name__=="__main__":
    unittest.main()
