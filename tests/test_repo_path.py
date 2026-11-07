"""The UI must import with only app_rewrite/ on sys.path, as the launcher runs it."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app_rewrite"


class CleanImportTest(unittest.TestCase):
    def test_ui_imports_without_repo_root_on_path(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        code = (
            "import sys; sys.path[0:1] = [%r]; import runtime, ui; print('CLEAN_IMPORT_OK')"
            % str(APP)
        )
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run(
                [sys.executable, "-c", code], cwd=cwd, env=env,
                capture_output=True, text=True, timeout=120,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("CLEAN_IMPORT_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
