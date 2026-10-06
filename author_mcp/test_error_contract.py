import unittest
from unittest.mock import patch
import mcp_server


class RaisingClient:
    error = RuntimeError("boom")

    def __init__(self, *args, **kwargs):
        pass

    def exchange(self, operation, payload=None, request_id=None):
        raise type(self).error


class ErrorContractTests(unittest.TestCase):
    def test_error_sources_are_deterministic(self):
        cases = {
            "PowerShellCommandError": "command",
            "CmdCommandError": "command",
            "SSHCommandCancelled": "command",
            "PowerShellSessionInterrupted": "shell",
            "CmdSessionInterrupted": "shell",
            "SSHSessionInterrupted": "shell",
            "ExecutionInterruptedByRestart": "executor",
            "PreparedStateLost": "executor",
            "MCPProtocolError": "mcp",
            "CodeBridgeRequestError": "executor",
            "TransportError": "transport",
            "CodeBridgeUnavailable": "transport",
        }
        for error_type, expected in cases.items():
            with self.subTest(error_type=error_type):
                self.assertEqual(
                    mcp_server._error_source(error_type), expected
                )

    def test_safe_exchange_classifies_transport(self):
        RaisingClient.error = RuntimeError(
            "adapter indisponivel: connection refused"
        )
        with patch.object(
            mcp_server, "ProtocolHTTPClient", RaisingClient
        ):
            exchange = mcp_server._safe_exchange(
                "EXECUTION_V2_STATUS",
                {"execution_id": "exec_transport"},
                timeout=1.0,
            )
        payload = exchange["payload"]
        self.assertFalse(payload["operation_ok"])
        self.assertEqual(payload["error_source"], "transport")
        self.assertEqual(payload["error_type"], "TransportError")
        self.assertTrue(payload["execution_recoverable"])
        self.assertEqual(payload["execution_id"], "exec_transport")

    def test_safe_exchange_classifies_mcp_protocol(self):
        RaisingClient.error = RuntimeError(
            "RESPONSE_ACK divergente em response_hash"
        )
        with patch.object(
            mcp_server, "ProtocolHTTPClient", RaisingClient
        ):
            exchange = mcp_server._safe_exchange(
                "EXECUTION_V2_START",
                {"target": "CMD", "command": "echo x"},
                timeout=1.0,
            )
        payload = exchange["payload"]
        self.assertEqual(payload["error_source"], "mcp")
        self.assertEqual(payload["error_type"], "MCPProtocolError")
        self.assertFalse(payload["execution_recoverable"])

    def test_exec_result_exposes_full_error_contract(self):
        exchange = {
            "request_syn": {"request_id": "req1"},
            "response_syn": {"response_id": "res1"},
        }
        payload = {
            "operation_ok": True,
            "state": "FAILED",
            "execution_id": "exec1",
            "target": "POWERSHELL5.1",
            "exit_code": 7,
            "output": "bad",
            "error_type": "PowerShellCommandError",
            "error_message": "falhou",
            "failed_command": 'cmd.exe /c "exit 7"',
            "shell_alive": True,
            "execution_recoverable": True,
        }
        result = mcp_server._exec_result(
            exchange, payload,
            target="POWERSHELL5.1",
            output_mode="NORMAL",
            wait_timeout_ms=1000,
        )
        self.assertEqual(result.error_source, "command")
        self.assertEqual(
            result.failed_command, 'cmd.exe /c "exit 7"'
        )
        self.assertTrue(result.shell_alive)
        self.assertTrue(result.execution_recoverable)
        self.assertEqual(result.exit_code, 7)

    def test_exec_start_error_uses_original_command(self):
        exchange = {
            "request_syn": {"request_id": "req2"},
            "response_syn": {"response_id": "res2"},
        }
        command = "Write-Output NEVER_STARTED"
        payload = {
            "operation_ok": False,
            "state": "ERROR",
            "error_type": "MCPProtocolError",
            "error_message": "handshake invalido",
        }
        result = mcp_server._exec_result(
            exchange, payload,
            target="POWERSHELL5.1",
            output_mode="NORMAL",
            wait_timeout_ms=1000,
            command=command,
        )
        self.assertEqual(result.error_source, "mcp")
        self.assertEqual(result.failed_command, command)
        self.assertFalse(result.execution_recoverable)
        self.assertIsNone(result.shell_alive)


if __name__ == "__main__":
    unittest.main()
