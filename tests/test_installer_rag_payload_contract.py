"""Installer must package the two offline RAG runtime diagnostics."""
import unittest
from pathlib import Path


class InstallerRuntimePayloadTests(unittest.TestCase):
    def test_diagnostic_scripts_in_installer_payload(self):
        root=Path(__file__).resolve().parents[1]
        config=(root/"installer"/"CodeBridge.nsi").read_text(encoding="utf-8")
        for filename in ("runtime_readiness.py", "runtime_staging_verify.py",
                         "runtime_maintenance_preflight.py", "runtime_fingerprints.py",
                         "runtime_recovery_archive.py", "runtime_postupdate_verify.py",
                         "runtime_full_restore_preflight.py"):
            self.assertTrue((root/"installer"/filename).is_file())
            self.assertIn('File "'+filename+'"',config)

    def test_bootstrap_exposes_project_root_and_pinned_qdrant(self):
        root=Path(__file__).resolve().parents[1]
        bootstrap=(root/"installer"/"bootstrap.ps1").read_text(encoding="utf-8")
        requirements=(root/"requirements.txt").read_text(encoding="utf-8")
        self.assertIn('"..\\.."',bootstrap)
        self.assertIn('qdrant-client==1.19.1',requirements)
        self.assertIn('qdrant_client,rag.contracts',bootstrap)
