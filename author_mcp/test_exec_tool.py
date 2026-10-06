import unittest
from unittest.mock import patch

import mcp_server


def exchange(operation, payload, index):
    return {
        "request_syn": {"request_id": f"req_{index}", "operation": operation},
        "response_syn": {"response_id": f"res_{index}"},
        "payload": payload,
    }


class FakeProtocolHTTPClient:
    responses = []
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def exchange(self, operation, payload=None, request_id=None):
        type(self).calls.append((operation, payload or {}))
        if not type(self).responses:
            raise AssertionError(f"unexpected exchange: {operation}")
        return type(self).responses.pop(0)


class CodeBridgeExecTests(unittest.TestCase):
    def setUp(self):
        FakeProtocolHTTPClient.responses = []
        FakeProtocolHTTPClient.calls = []

    def test_fast_execution_returns_final_result(self):
        FakeProtocolHTTPClient.responses = [
            exchange(
                "EXECUTION_V2_START",
                {
                    "operation_ok": True,
                    "execution_id": "exec_fast",
                    "target": "POWERSHELL5.1",
                    "state": "CREATED",
                },
                1,
            ),
            exchange(
                "EXECUTION_V2_STATUS",
                {
                    "operation_ok": True,
                    "execution_id": "exec_fast",
                    "target": "POWERSHELL5.1",
                    "state": "FINISHED",
                    "started_at": "2026-10-05T20:00:00+00:00",
                    "finished_at": "2026-10-05T20:00:00.250000+00:00",
                    "complete": True,
                },
                2,
            ),
            exchange(
                "EXECUTION_V2_RESULT",
                {
                    "operation_ok": True,
                    "execution_id": "exec_fast",
                    "state": "FINISHED",
                    "ready": True,
                    "output": "OK\n",
                    "exit_code": 0,
                    "error_type": None,
                    "error_message": None,
                    "finished_at": "2026-10-05T20:00:00.250000+00:00",
                },
                3,
            ),
        ]

        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeProtocolHTTPClient,
        ), patch.object(mcp_server.time, "sleep", return_value=None):
            result = mcp_server.codebridge_exec(
                "POWERSHELL5.1",
                "Write-Output 'OK'",
                wait_timeout_ms=1500,
            )

        self.assertEqual(result.state, "FINISHED")
        self.assertEqual(result.runtime_state, "FINISHED")
        self.assertTrue(result.complete)
        self.assertEqual(result.execution_id, "exec_fast")
        self.assertEqual(result.target, "POWERSHELL5.1")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "OK\n")
        self.assertEqual(result.duration_ms, 250)
        self.assertTrue(result.raw_available)
        self.assertEqual(
            [call[0] for call in FakeProtocolHTTPClient.calls],
            [
                "EXECUTION_V2_START",
                "EXECUTION_V2_STATUS",
                "EXECUTION_V2_RESULT",
            ],
        )

    def test_timeout_returns_running_without_reexecution(self):
        FakeProtocolHTTPClient.responses = [
            exchange(
                "EXECUTION_V2_START",
                {
                    "operation_ok": True,
                    "execution_id": "exec_long",
                    "target": "SSH",
                    "state": "CREATED",
                },
                1,
            ),
        ]

        with patch.object(
            mcp_server,
            "ProtocolHTTPClient",
            FakeProtocolHTTPClient,
        ), patch.object(
            mcp_server.time,
            "monotonic",
            side_effect=[100.0, 100.1],
        ):
            result = mcp_server.codebridge_exec(
                "SSH",
                "sleep 30",
                wait_timeout_ms=10,
            )

        self.assertEqual(result.state, "RUNNING")
        self.assertEqual(result.runtime_state, "CREATED")
        self.assertFalse(result.complete)
        self.assertEqual(result.execution_id, "exec_long")
        self.assertEqual(result.output, "")
        self.assertTrue(result.raw_available)
        self.assertEqual(
            [call[0] for call in FakeProtocolHTTPClient.calls],
            ["EXECUTION_V2_START"],
        )

    def test_prod_001_rejects_future_output_modes(self):
        with self.assertRaises(ValueError):
            mcp_server.codebridge_exec(
                "CMD",
                "echo test",
                output_mode="COMPACT",
            )



if __name__ == "__main__":
    unittest.main()
