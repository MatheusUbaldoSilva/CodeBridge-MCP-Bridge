"""Offline MCP overlay smoke contract, without an actual installed process."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from benchmarks.rag_p9b_offline_overlay_smoke import smoke_verified_overlay
from installer.rag_p9b_mcp_overlay import OVERLAY_FILES


class OfflineOverlaySmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge"
        for directory in ("rag", "author_mcp", "runtime/python"):
            (self.root / directory).mkdir(parents=True)
        (self.root / "runtime/python/python.exe").write_bytes(b"synthetic")
        self.bundle = Path(self.temp.name) / "archive.zip"
        with ZipFile(self.bundle, "w") as archive:
            for rel in OVERLAY_FILES:
                archive.writestr("new/"+rel,b"# synthetic overlay\n")

    def test_invalid_bundle_refused_before_execution(self):
        with patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.verify_mcp_bootstrap_overlay",
            return_value={"valid": False},
        ), patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.subprocess.run",
            side_effect=AssertionError("Python must not run"),
        ):
            result = smoke_verified_overlay(self.bundle, self.root)
        self.assertEqual(result["state"], "OVERLAY_UNVERIFIED")
        self.assertFalse(result["installed_modified"])

    def test_missing_portable_python_refused(self):
        (self.root / "runtime/python/python.exe").unlink()
        with patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.verify_mcp_bootstrap_overlay",
            return_value={"valid": True},
        ):
            report = smoke_verified_overlay(self.bundle,self.root)
        self.assertEqual(report["state"], "PORTABLE_PYTHON_UNAVAILABLE")

    def test_staged_python_result_is_not_reported_as_live_deployment(self):
        fake = json.dumps({
            "state": "OFFLINE_MCP_OVERLAY_SMOKE_PASS",
            "tool_count": 18,
            "preview_state": "BOOTSTRAP_PLAN_ONLY",
            "registered_tool": "codebridge_rag_queue_bootstrap",
        })
        with patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.verify_mcp_bootstrap_overlay",
            return_value={"valid": True},
        ), patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=fake, stderr=""),
        ):
            result = smoke_verified_overlay(self.bundle,self.root)
        self.assertEqual(result["state"],"OFFLINE_MCP_OVERLAY_SMOKE_PASS")
        self.assertFalse(result["installed_modified"])
        self.assertFalse(result["mcp_restarted"])
        self.assertFalse(result["queue_initialized"])

    def test_failed_import_is_explicit_and_no_mutations_claimed(self):
        with patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.verify_mcp_bootstrap_overlay",
            return_value={"valid": True},
        ), patch(
            "benchmarks.rag_p9b_offline_overlay_smoke.subprocess.run",
            return_value=SimpleNamespace(returncode=2, stdout="", stderr="bad import"),
        ):
            result = smoke_verified_overlay(self.bundle,self.root)
        self.assertEqual(result["state"], "STAGED_MCP_IMPORT_FAILED")
        self.assertFalse(result["installed_modified"])


if __name__ == "__main__":
    unittest.main()
