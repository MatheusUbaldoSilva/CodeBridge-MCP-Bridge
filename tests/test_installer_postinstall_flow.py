import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class InstallerPostInstallFlowTests(unittest.TestCase):
    def test_installer_starts_codebridge_before_extension_check(self):
        text = (ROOT / "installer" / "CodeBridge.nsi").read_text(encoding="utf-8-sig")
        self.assertIn("Unicode True", text)
        self.assertIn("--ensure-codebridge", text)
        self.assertLess(text.index("--ensure-codebridge"), text.index("--needs-attention"))
        self.assertIn("instala\u00e7\u00e3o existente", text)
        self.assertNotIn("\u00c3\u0192", text)
        self.assertNotIn("\u00c3\u00a7", text)

    def test_extension_assistant_can_start_runtime_and_blocks_early_test(self):
        text = (ROOT / "installer" / "extension_setup.py").read_text(encoding="utf-8")
        self.assertIn("def ensure_codebridge(", text)
        self.assertIn('self.start_button = QPushButton("Iniciar CodeBridge")', text)
        self.assertIn("self.test_button.setEnabled(companion_ok)", text)
        self.assertIn('"--ensure-codebridge" in sys.argv', text)
        self.assertIn('"CodeBridge: "', text)
        self.assertNotIn("\u00c3\u0192", text)
        self.assertNotIn("\u00e2\u20ac", text)

if __name__ == "__main__":
    unittest.main()
