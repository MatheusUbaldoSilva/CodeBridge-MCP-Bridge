"""Offline tests for the independent CodeBridge launcher."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launcher


class LauncherTests(unittest.TestCase):
    def test_real_dev_preflight(self):
        root, python = launcher.verify("dev", require_idle=True)
        self.assertTrue((root / "app_rewrite" / "main.py").is_file())
        self.assertTrue(python.is_file())

    def test_real_stable_integrity(self):
        info = launcher.check_snapshot()
        self.assertEqual(info["state"], "CANDIDATE")
        self.assertEqual(len(info["checksums"]), 978)
        self.assertFalse(info["promotion_authorized"])

    def test_integrity_fails_closed_on_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "snap"
            root.mkdir()
            file = root / "test.py"
            file.write_text("ok", encoding="utf-8")
            target = Path(temp) / "manifest.json"
            target.write_text(json.dumps({
                "state": "CANDIDATE",
                "checksums": {"test.py": hashlib.sha256(file.read_bytes()).hexdigest()},
            }), encoding="utf-8")
            with patch.object(launcher, "STABLE", root), patch.object(launcher, "MANIFEST", target):
                launcher.check_snapshot()
                file.write_text("tampered", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "Integridade falhou"):
                    launcher.check_snapshot()

    def test_prevent_duplicate_application(self):
        with patch.object(launcher, "app_running", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "Ja existe"):
                launcher.verify("dev", require_idle=True)

    def test_gui_can_open_and_close(self):
        app = launcher.Launcher()
        app.root.after(400, app.close)
        app.run()


if __name__ == "__main__":
    unittest.main(verbosity=2)
