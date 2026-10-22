"""Read-only restart path checks."""
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_restart_readiness import inspect_restart_prerequisites, REQUIRED


class RestartReadinessTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)/"CodeBridge"
        self.root.mkdir()

    def install_stub(self):
        for rel in REQUIRED:
            path=self.root/rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b"ok")

    def test_fully_present_is_only_observed(self):
        self.install_stub()
        r=inspect_restart_prerequisites(self.root)
        self.assertEqual(r["state"],"RESTART_FILES_OBSERVED_ONLY")
        self.assertFalse(r["restarted"])
        self.assertFalse(r["safe_to_update"])

    def test_missing_python_blocks(self):
        self.install_stub()
        (self.root/"runtime/python/pythonw.exe").unlink()
        r=inspect_restart_prerequisites(self.root)
        self.assertEqual(r["reason"],"RESTART_COMPONENT_MISSING")
        self.assertIn("runtime/python/pythonw.exe",r["missing"])

    def test_absent_install_root_blocks(self):
        r=inspect_restart_prerequisites(self.root/"missing")
        self.assertEqual(r["reason"],"INSTALL_ROOT_NOT_FOUND")

    def test_zero_length_file_is_missing(self):
        self.install_stub()
        (self.root/"author_mcp/mcp_server.py").write_bytes(b"")
        r=inspect_restart_prerequisites(self.root)
        self.assertIn("author_mcp/mcp_server.py",r["missing"])


if __name__=="__main__":
    unittest.main()
