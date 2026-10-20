import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime_maintenance_preflight import assess_runtime_maintenance

_PUBLIC_BASELINE = {"files": {
    "rag_manifest": {"exists": True, "sha256": "a", "bytes": 1},
    "rag_sqlite": {"exists": True, "sha256": "b", "bytes": 2},
            "rag_qdrant": {"exists": True, "sha256": "q", "bytes": 3, "file_count": 2},
            "rag_qdrant": {"exists": True, "sha256": "q", "bytes": 3, "file_count": 2},
}}


class MaintenancePreflightTests(unittest.TestCase):
    def test_blocked_without_valid_stage(self):
        with patch("installer.runtime_maintenance_preflight.collect_runtime_fingerprints",
                   return_value=_PUBLIC_BASELINE), patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": False, "errors": ["MISSING_MODULE_RAG"]}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": False}):
            result = assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"], "MAINTENANCE_BLOCKED")
        self.assertFalse(result["installed_files_changed"])

    def test_staged_validation_needs_operator_maintenance(self):
        with patch("installer.runtime_maintenance_preflight.collect_runtime_fingerprints",
                   return_value=_PUBLIC_BASELINE), patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": False}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": True}):
            result=assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"],"OFFLINE_MAINTENANCE_CANDIDATE")
        self.assertTrue(result["requires_codebridge_closed"])
        self.assertTrue(result["operator_approval_required"])
        self.assertFalse(result["applied"])
        self.assertFalse(result["stop_requested"])
        self.assertFalse(result["full_rollback_verified"])
        self.assertFalse(result["maintenance_execution_authorized"])

    def test_existing_ready_install_does_not_request_maintenance(self):
        with patch("installer.runtime_maintenance_preflight.collect_runtime_fingerprints",
                   return_value=_PUBLIC_BASELINE), patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": True}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": False}):
            result=assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"],"READY_ALREADY_INSTALLED")
        self.assertFalse(result["operator_approval_required"])
        self.assertFalse(result["public_index_updated"])

    def test_missing_public_baseline_blocks_maintenance(self):
        with patch("installer.runtime_maintenance_preflight.collect_runtime_fingerprints",
                   return_value={"files": {
                       "rag_manifest": {"exists": False},
                       "rag_sqlite": {"exists": True}}}), patch(
                   "installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": False}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": True}):
            result=assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"],"MISSING_PUBLIC_INDEX_BASELINE")
        self.assertFalse(result["applied"])
