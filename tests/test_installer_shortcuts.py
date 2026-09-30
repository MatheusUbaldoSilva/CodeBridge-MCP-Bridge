import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NSI = ROOT / "installer" / "CodeBridge.nsi"


class InstallerShortcutTests(unittest.TestCase):
    def test_updates_always_repair_shortcuts(self):
        text = NSI.read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn(
            "IfSilent shortcuts_done",
            text,
        )
        self.assertIn(
            'CreateShortcut "$DESKTOP\\CodeBridge 2.0 - MCP Bridge.lnk"',
            text,
        )
        self.assertIn(
            '"$INSTDIR\\runtime\\python\\pythonw.exe"',
            text,
        )
        self.assertIn(
            ''"$INSTDIR\\app_rewrite\\main.py"'',
            text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
