import unittest
from unittest.mock import patch

import mcp_server


class FakeClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def exchange(self, operation, payload=None, request_id=None):
        type(self).calls.append(
            (operation, payload or {})
        )
        if operation == "STATUS":
            data = {
                "operation_ok": True,
                "app": "CodeBridge Test",
                "version": "9.9.9-test",
            }
        elif operation == "EXECUTION_V2_STOP":
            data = {
                "operation_ok": True,
                "execution_id": (payload or {}).get(
                    "execution_id"
                ),
                "cancelled": True,
                "state": "CANCELLED",
                "reason": "ctrl_c_sent",
            }
        elif operation == "STOP":
            data = {
                "operation_ok": True,
                "cancelled": True,
                "reason": "active_stopped",
            }
        else:
            raise AssertionError(operation)
        return {
            "request_syn": {
                "request_id": "req_test",
                "operation": operation,
            },
            "response_syn": {
                "response_id": "res_test",
            },
            "payload": data,
        }


class MigrationCatalogTests(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []

    def test_capabilities_exposes_preferred_and_legacy_catalog(self):
        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeClient,
        ):
            result = mcp_server.codebridge_capabilities()

        self.assertEqual(result.protocol, "CBMCP/1")
        self.assertEqual(result.app, "CodeBridge Test")
        self.assertEqual(result.version, "9.9.9-test")
        self.assertEqual(
            result.targets,
            ["POWERSHELL5.1", "CMD", "SSH"],
        )
        self.assertTrue(result.features["wait"])
        self.assertTrue(
            result.features["targeted_cancel"]
        )
        self.assertTrue(
            result.features["read_only_batch"]
        )
        self.assertEqual(
            result.limits["wait_timeout_max_ms"],
            120000,
        )
        self.assertEqual(
            result.limits["read_batch_max_workers"],
            8,
        )
        self.assertIn(
            "codebridge_exec",
            result.preferred_tools,
        )
        self.assertIn(
            "codebridge_stop",
            result.preferred_tools,
        )
        legacy = {
            item["name"]: item["replacement"]
            for item in result.legacy_tools
        }
        self.assertEqual(
            legacy["codebridge_v2_stop"],
            "codebridge_stop(execution_id=...)",
        )
        self.assertEqual(
            result.migration["stage"],
            "REMOVE",
        )
        self.assertFalse(
            result.migration["legacy_tools_published"]
        )
        self.assertTrue(
            result.migration["legacy_removal_ready"]
        )
        self.assertEqual(
            FakeClient.calls,
            [("STATUS", {})],
        )

    def test_legacy_tool_exports_are_removed(self):
        removed = [
            "codebridge_ping",
            "codebridge_terminal",
            "codebridge_start",
            "codebridge_execution_status",
            "codebridge_v2_start",
            "codebridge_v2_status",
            "codebridge_v2_result",
            "codebridge_v2_output",
            "codebridge_v2_stop",
        ]
        for name in removed:
            self.assertFalse(
                hasattr(mcp_server, name),
                name,
            )


    def test_targeted_stop_replaces_v2_stop(self):
        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeClient,
        ):
            result = mcp_server.codebridge_stop(
                "exec_target"
            )

        self.assertTrue(result.cancelled)
        self.assertTrue(result.targeted)
        self.assertEqual(
            result.execution_id,
            "exec_target",
        )
        self.assertEqual(result.state, "CANCELLED")
        self.assertEqual(
            FakeClient.calls,
            [(
                "EXECUTION_V2_STOP",
                {"execution_id": "exec_target"},
            )],
        )

    def test_global_stop_remains_backward_compatible(self):
        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeClient,
        ):
            result = mcp_server.codebridge_stop()

        self.assertTrue(result.cancelled)
        self.assertFalse(result.targeted)
        self.assertIsNone(result.execution_id)
        self.assertEqual(
            result.reason,
            "active_stopped",
        )
        self.assertEqual(
            FakeClient.calls,
            [("STOP", {})],
        )


if __name__ == "__main__":
    unittest.main()