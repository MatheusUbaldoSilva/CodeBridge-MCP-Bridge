"""Isolated runtime verification never writes to installed Python."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from installer.runtime_staging_verify import verify_staged_embedded_runtime


class IsolatedRuntimeVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.install = root / "installed"
        self.repo = root / "repository"
        self.stage = root / "isolated"
        (self.install / "runtime" / "python").mkdir(parents=True)
        (self.install / "runtime" / "python" / "python.exe").write_bytes(b"test")
        (self.repo / "rag").mkdir(parents=True)
        (self.repo / "rag" / "__init__.py").write_text("")
        (self.stage / "qdrant_client").mkdir(parents=True)

    def test_import_success_is_not_install_success(self):
        result = json.dumps({"qdrant_version":"1.19.1","worker_ready":True,
                             "validator_ready":True})
        with patch("installer.runtime_staging_verify.subprocess.run",
                   return_value=SimpleNamespace(returncode=0,stdout=result,stderr="")):
            status=verify_staged_embedded_runtime(self.install,self.repo,self.stage)
        self.assertEqual(status["state"],"STAGING_IMPORTS_VALIDATED")
        self.assertFalse(status["live_runtime_updated"])
        self.assertFalse(status["public_index_updated"])

    def test_wrong_version_fails_closed(self):
        output=json.dumps({"qdrant_version":"0.0.1","worker_ready":True,
                           "validator_ready":True})
        with patch("installer.runtime_staging_verify.subprocess.run",
                   return_value=SimpleNamespace(returncode=0,stdout=output)):
            result=verify_staged_embedded_runtime(self.install,self.repo,self.stage)
        self.assertFalse(result["validated"])

    def test_staging_inside_installed_runtime_is_rejected(self):
        nested=self.install/"runtime"/"python"/"dependencies"
        (nested/"qdrant_client").mkdir(parents=True)
        with patch("installer.runtime_staging_verify.subprocess.run") as runner:
            result=verify_staged_embedded_runtime(self.install,self.repo,nested)
        self.assertEqual(result["state"],"STAGING_NOT_ISOLATED")
        runner.assert_not_called()

    def test_missing_dependencies_never_runs_probe(self):
        with patch("installer.runtime_staging_verify.subprocess.run") as runner:
            result=verify_staged_embedded_runtime(
                self.install,self.repo,self.stage/"missing")
        self.assertEqual(result["state"],"STAGING_UNAVAILABLE")
        runner.assert_not_called()
