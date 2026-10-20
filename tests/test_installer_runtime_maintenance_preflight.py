import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime_maintenance_preflight import assess_runtime_maintenance


class MaintenancePreflightTests(unittest.TestCase):
    def test_blocked_without_valid_stage(self):
        with patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": False, "errors": ["MISSING_MODULE_RAG"]}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": False}):
            result = assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"], "MAINTENANCE_BLOCKED")
        self.assertFalse(result["installed_files_changed"])

    def test_staged_validation_needs_operator_maintenance(self):
        with patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": False}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": True}):
            result=assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"],"OFFLINE_MAINTENANCE_CANDIDATE")
        self.assertTrue(result["requires_codebridge_closed"])
        self.assertTrue(result["operator_approval_required"])
        self.assertFalse(result["applied"])
        self.assertFalse(result["stop_requested"])

    def test_existing_ready_install_does_not_request_maintenance(self):
        with patch("installer.runtime_maintenance_preflight.inspect_embedded_runtime",
                   return_value={"ready": True}), patch(
                   "installer.runtime_maintenance_preflight.verify_staged_embedded_runtime",
                   return_value={"validated": False}):
            result=assess_runtime_maintenance(Path("C:/a"),Path("C:/b"),Path("C:/c"))
        self.assertEqual(result["state"],"READY_ALREADY_INSTALLED")
        self.assertFalse(result["operator_approval_required"])
        self.assertFalse(result["public_index_updated"])
