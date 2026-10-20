"""Read-only embedded runtime diagnostics regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from installer.runtime_readiness import inspect_embedded_runtime, MODULES


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / "runtime" / "python"
        self.runtime.mkdir(parents=True)
        (self.runtime / "python.exe").write_bytes(b"fixture")
        self.pth = self.runtime / "python313._pth"

    def fake_probe(self, present):
        return SimpleNamespace(returncode=0, stdout=json.dumps(
            {name: name in present for name in MODULES}), stderr="")

    def test_missing_pth_is_blocked_without_creation(self):
        with patch("installer.runtime_readiness.subprocess.run") as run:
            result = inspect_embedded_runtime(self.root)
        self.assertIn("RUNTIME_OR_PTH_MISSING", result["errors"])
        self.assertFalse(self.pth.exists())
        run.assert_not_called()

    def test_legacy_installed_layout_is_not_ready(self):
        self.pth.write_text("python313.zip\n.\nLib\\site-packages\nimport site\n")
        with patch("installer.runtime_readiness.subprocess.run",
                   return_value=self.fake_probe(("PySide6", "psutil", "paramiko"))):
            result=inspect_embedded_runtime(self.root)
        self.assertEqual(
            set(result["errors"]),
            {"INSTALL_ROOT_NOT_ON_PYTHON_PATH", "MISSING_MODULE_RAG",
             "MISSING_MODULE_QDRANT_CLIENT"})
        self.assertFalse(result["modifies_runtime"])

    def test_complete_runtime_is_ready(self):
        self.pth.write_text("python313.zip\n.\nLib\\site-packages\n..\\..\nimport site\n")
        with patch("installer.runtime_readiness.subprocess.run",
                   return_value=self.fake_probe(MODULES)):
            result=inspect_embedded_runtime(self.root)
        self.assertTrue(result["ready"])
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["modifies_runtime"])

    def test_bad_python_probe_does_not_claim_ready(self):
        self.pth.write_text("..\\..\n")
        with patch("installer.runtime_readiness.subprocess.run",
                   return_value=SimpleNamespace(returncode=1,stdout="",stderr="failure")):
            result=inspect_embedded_runtime(self.root)
        self.assertIn("PYTHON_PROBE_FAILED",result["errors"])
        self.assertFalse(result["ready"])
