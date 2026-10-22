import tempfile
import subprocess
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from installer.rag_p9b_mcp_overlay import (
    OVERLAY_FILES, stage_mcp_bootstrap_overlay, verify_mcp_bootstrap_overlay,
)


class OfflineOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "CodeBridge-MCP-Bridge"
        self.installed = self.root / "Programs" / "CodeBridge"
        self.src.mkdir()
        (self.src / ".git").mkdir()
        self.installed.mkdir(parents=True)
        for rel in OVERLAY_FILES:
            file = self.src / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"NEW:"+rel.encode())
            if rel in ("author_mcp/mcp_server.py", "rag/runtime/incremental_job_queue.py"):
                target = self.installed / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"OLD:"+rel.encode())
        subprocess.run(["git","init","-q",str(self.src)], check=True)
        subprocess.run(["git","-C",str(self.src),"add","."], check=True)
        subprocess.run(["git","-C",str(self.src),"-c","user.name=Test",
                        "-c","user.email=test@example.invalid",
                        "commit","-q","-m","approved package"], check=True)
        self.archive = self.root / "MCP_p9b_overlay.zip"

    def test_staged_bundle_has_verified_byte_exact_recovery(self):
        before = {
            rel: (self.installed / rel).read_bytes()
            for rel in OVERLAY_FILES if (self.installed / rel).is_file()
        }
        result = stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)
        self.assertEqual(result["state"], "OFFLINE_OVERLAY_STAGED")
        self.assertTrue(self.archive.is_file())
        self.assertEqual(
            verify_mcp_bootstrap_overlay(self.archive, self.installed)["state"],
            "OVERLAY_VERIFIED_AND_NOT_INSTALLED",
        )
        self.assertEqual(
            before, {rel: (self.installed / rel).read_bytes() for rel in before},
        )
        self.assertFalse((self.installed / "rag" / "runtime" /
                          "incremental_authorized_queue_bootstrap.py").exists())

    def test_stale_installed_file_fails_verification(self):
        stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)
        (self.installed / "author_mcp" / "mcp_server.py").write_bytes(b"RACE")
        self.assertFalse(
            verify_mcp_bootstrap_overlay(self.archive, self.installed)["valid"],
        )

    def test_refuses_any_overwrite_and_output_inside_installed(self):
        nested = self.installed / "payload.zip"
        self.assertEqual(
            stage_mcp_bootstrap_overlay(self.src, self.installed, nested)["state"],
            "OVERLAY_STAGE_BLOCKED",
        )
        self.assertFalse(nested.exists())
        self.archive.write_bytes(b"existing")
        self.assertEqual(
            stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)["state"],
            "OVERLAY_STAGE_BLOCKED",
        )
        self.assertEqual(self.archive.read_bytes(), b"existing")

    def test_missing_existing_baseline_blocks(self):
        (self.installed / "author_mcp" / "mcp_server.py").unlink()
        self.assertFalse(
            stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)["created"]
        )
        self.assertFalse(self.archive.exists())

    def test_uncommitted_replacement_must_not_be_packaged(self):
        path = self.src / "rag" / "runtime" / "incremental_authorized_queue_bootstrap.py"
        path.write_bytes(b"DIRTY_UNCOMMITTED")
        value = stage_mcp_bootstrap_overlay(self.src,self.installed,self.archive)
        self.assertEqual(value["state"],"OVERLAY_STAGE_BLOCKED")
        self.assertFalse(self.archive.exists())

    def test_untrusted_source_is_not_packaged(self):
        (self.src / "rag" / "runtime" /
         "incremental_authorized_queue_bootstrap.py").unlink()
        self.assertFalse(
            stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)["created"]
        )

    def test_refuses_archive_with_unrecognized_entries(self):
        stage_mcp_bootstrap_overlay(self.src, self.installed, self.archive)
        with ZipFile(self.archive, "a", ZIP_DEFLATED) as output:
            output.writestr("unexpected", b"bad")
        self.assertFalse(
            verify_mcp_bootstrap_overlay(self.archive, self.installed)["valid"]
        )


if __name__ == "__main__":
    unittest.main()
