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
        root, python = launcher.verify("dev", require_idle=False)
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

    def test_unlisted_source_blocks_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stable"
            root.mkdir()
            main = root / "main.py"
            main.write_text("print('ok')", encoding="utf-8")
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({
                "state": "CANDIDATE",
                "checksums": {"main.py": hashlib.sha256(main.read_bytes()).hexdigest()},
            }), encoding="utf-8")
            with patch.object(launcher, "STABLE", root), patch.object(launcher, "MANIFEST", manifest):
                launcher.check_snapshot()
                (root / "unexpected.py").write_text("print('unsafe')", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "Arquivo nao verificado"):
                    launcher.check_snapshot()

    def test_manifest_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stable"
            root.mkdir()
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({
                "state": "CANDIDATE",
                "checksums": {"../outside.py": hashlib.sha256(b"x").hexdigest()},
            }), encoding="utf-8")
            with patch.object(launcher, "STABLE", root), patch.object(launcher, "MANIFEST", manifest):
                with self.assertRaisesRegex(RuntimeError, "Entrada insegura"):
                    launcher.check_snapshot()

    def test_dev_failure_does_not_destroy_stable_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            missing_dev = Path(temp) / "broken_dev"
            with patch.object(launcher, "DEV", missing_dev):
                with self.assertRaisesRegex(RuntimeError, "Dependencia ausente"):
                    launcher.verify("dev", require_idle=False)
            self.assertEqual(launcher.check_snapshot()["state"], "CANDIDATE")

    def test_prevent_duplicate_application(self):
        with patch.object(launcher, "app_running", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "Ja existe"):
                launcher.verify("dev", require_idle=True)

    def test_gui_can_open_and_close(self):
        # Independent GUI smoke, without acquiring the real shared launcher mutex.
        with patch.object(launcher.KERNEL, "CreateMutexW", return_value=1), \
             patch.object(launcher.KERNEL, "CloseHandle", return_value=True), \
             patch.object(launcher.ctypes, "get_last_error", return_value=0):
            app = launcher.Launcher()
            app.root.after(400, app.close)
            app.run()


if __name__ == "__main__":
    unittest.main(verbosity=2)
