"""P9-B Git-only installer export tests, never invoking NSIS."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from installer.rag_p9b_clean_release import export_committed_release, build_p9b_preview


class CleanInstallerExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "project"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        tracked = self.repo / "rag" / "runtime" / "safe.py"
        tracked.parent.mkdir(parents=True)
        tracked.write_text("version = 1\n", encoding="utf-8")
        (self.repo / "author_mcp").mkdir()
        (self.repo / "author_mcp" / "mcp_server.py").write_text(
            "print('server')\n", encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.repo), "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "commit", "-q", "-m", "known safe",
        ], check=True)
        self.destination = self.base / "export"

    def test_git_export_ignores_dirty_and_untracked_python(self):
        tracked = self.repo / "rag" / "runtime" / "safe.py"
        tracked.write_text("version = 999\n", encoding="utf-8")
        untracked = self.repo / "rag" / "runtime" / "unsafe_untracked.py"
        untracked.write_text("dangerous()\n", encoding="utf-8")
        result = export_committed_release(self.repo, self.destination)
        self.assertEqual(result["state"], "COMMITTED_TREE_EXPORTED")
        self.assertTrue(result["exported"])
        self.assertEqual(
            (self.destination / "rag" / "runtime" / "safe.py").read_text(),
            "version = 1\n",
        )
        self.assertFalse(
            (self.destination / "rag" / "runtime" / "unsafe_untracked.py").exists(),
        )
        self.assertEqual(untracked.read_text(), "dangerous()\n")

    def test_existing_export_is_never_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / "preserve.txt"
        marker.write_text("keep")
        result = export_committed_release(self.repo, self.destination)
        self.assertEqual(result["state"], "EXPORT_REFUSED")
        self.assertEqual(marker.read_text(), "keep")

    def test_output_inside_repo_must_not_run_without_toolchain(self):
        out = self.repo / "installer.exe"
        result = build_p9b_preview(
            self.repo, self.base,
            out, self.base / "absent-makensis.exe",
            self.base / "absent-7z.exe",
        )
        self.assertEqual(result["state"], "CLEAN_INSTALLER_BUILD_FAILED")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
