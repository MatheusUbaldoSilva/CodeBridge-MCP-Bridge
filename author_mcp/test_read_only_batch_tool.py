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
        return {
            "request_syn": {
                "request_id": "req_batch",
                "operation": operation,
            },
            "response_syn": {
                "response_id": "res_batch",
            },
            "payload": {
                "operation_ok": True,
                "count": 2,
                "ok_count": 2,
                "error_count": 0,
                "complete": True,
                "read_only": True,
                "items": [
                    {
                        "index": 0,
                        "id": "v",
                        "kind": "VERSION",
                        "ok": True,
                        "result": {
                            "app": "CodeBridge",
                            "version": "x",
                        },
                        "error_type": None,
                        "error_message": None,
                    },
                    {
                        "index": 1,
                        "id": "s",
                        "kind": "FILE_STAT",
                        "ok": True,
                        "result": {"size": 1},
                        "error_type": None,
                        "error_message": None,
                    },
                ],
            },
        }


class ReadOnlyBatchToolTests(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []

    def test_one_tool_call_is_one_batch_exchange(self):
        operations = [
            {"id": "v", "kind": "VERSION"},
            {
                "id": "s",
                "kind": "FILE_STAT",
                "path": "x",
            },
        ]
        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeClient,
        ):
            result = mcp_server.codebridge_read_batch(
                operations
            )

        self.assertTrue(result.read_only)
        self.assertTrue(result.complete)
        self.assertEqual(result.count, 2)
        self.assertEqual(result.ok_count, 2)
        self.assertEqual(
            FakeClient.calls,
            [("READ_ONLY_BATCH", {
                "operations": operations
            })],
        )


if __name__ == "__main__":
    unittest.main()