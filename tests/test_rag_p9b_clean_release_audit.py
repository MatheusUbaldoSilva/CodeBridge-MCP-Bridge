import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from installer.rag_p9b_clean_release_audit import audit_p9b_nsis_payload

COMMIT = "a" * 40


class NsIsPayloadAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / "P9B-Clean.exe"
        self.exe.write_bytes(b"MZsynthetic")
        self.zip = self.root / "7z.exe"
        self.zip.write_bytes(b"synthetic")

    def inspect(self, **kwargs):
        return audit_p9b_nsis_payload(
            self.root, self.exe, self.zip,
            expected_commit=kwargs.get("commit", COMMIT),
        )

    def test_invalid_commit_never_runs_toolchain(self):
        with patch(
            "installer.rag_p9b_clean_release_audit.subprocess.run",
            side_effect=AssertionError("toolchain must not be called"),
        ):
            result = self.inspect(commit="latest")
        self.assertEqual(result["state"], "P9B_NSIS_PAYLOAD_UNVERIFIED")
        self.assertFalse(result["installer_executed"])

    def test_missing_installer_fails_before_extract(self):
        self.exe.unlink()
        with patch(
            "installer.rag_p9b_clean_release_audit.subprocess.run",
            side_effect=AssertionError("no extraction"),
        ):
            result = self.inspect()
        self.assertFalse(result["verified"])

    def test_untracked_python_draft_rejected_from_binary_listing(self):
        tracked = CompletedProcess([], 0, stdout="author_mcp/mcp_server.py\n")
        binary = CompletedProcess([], 0, stdout=(
            "Path = author_mcp\\mcp_server.py\n"
            "Path = rag\\runtime\\incremental_installed_queue_init.py\n"
        ))
        with patch(
            "installer.rag_p9b_clean_release_audit.subprocess.run",
            side_effect=[tracked, binary],
        ) as run:
            result = self.inspect()
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"], "UNCOMMITTED_OR_MISSING_PYTHON")
        self.assertIn("rag/runtime/incremental_installed_queue_init.py",
                      result["unexpected"])
        self.assertEqual(run.call_count, 2)
        self.assertFalse(result["installed_modified"])


if __name__ == "__main__":
    unittest.main()
