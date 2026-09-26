import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapter_server import AdapterState
from protocol import PROTOCOL_VERSION, sha256_payload


class TurnControlAdapterTests(unittest.TestCase):
    def test_turn_control_is_added_to_success_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = AdapterState(
                ledger_path=Path(tmp) / "ledger.db",
                operations={
                    "TEST": lambda payload, request_id=None: {
                        "value": 123,
                    }
                },
            )

            request_id = "req_turn_control_success"
            payload = {}
            request_syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "REQUEST_SYN",
                "request_id": request_id,
                "operation": "TEST",
                "payload": payload,
                "request_hash": sha256_payload(payload),
            }

            state.receive_request(request_syn)

            expected = {
                "stage": "WRAP_UP_NOW",
                "action": "FINISH_RESPONSE_NORMALLY",
                "request_wrap_up": True,
                "directive": "checkpoint",
            }

            with patch(
                "adapter_server.codebridge_turn_control",
                return_value=expected,
            ):
                response = state.response_syn(request_id)

            result = response["payload"]
            self.assertTrue(result["operation_ok"])
            self.assertEqual(
                result["turn_control"],
                expected,
            )

    def test_turn_control_is_added_to_error_response(self):
        def fail(payload, request_id=None):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as tmp:
            state = AdapterState(
                ledger_path=Path(tmp) / "ledger.db",
                operations={"TEST": fail},
            )

            request_id = "req_turn_control_error"
            payload = {}
            request_syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "REQUEST_SYN",
                "request_id": request_id,
                "operation": "TEST",
                "payload": payload,
                "request_hash": sha256_payload(payload),
            }

            state.receive_request(request_syn)

            expected = {
                "stage": "WRAP_UP_NOW",
                "action": "FINISH_RESPONSE_NORMALLY",
                "request_wrap_up": True,
                "directive": "checkpoint",
            }

            with patch(
                "adapter_server.codebridge_turn_control",
                return_value=expected,
            ):
                response = state.response_syn(request_id)

            result = response["payload"]
            self.assertFalse(result["operation_ok"])
            self.assertEqual(
                result["error_type"],
                "RuntimeError",
            )
            self.assertEqual(
                result["turn_control"],
                expected,
            )

    def test_wrap_up_blocks_new_execution(self):
        calls = []

        def start(payload, request_id=None):
            calls.append(
                (payload, request_id)
            )
            return {"started": True}

        with tempfile.TemporaryDirectory() as tmp:
            state = AdapterState(
                ledger_path=Path(tmp) / "ledger.db",
                operations={
                    "EXECUTION_V2_START": start,
                },
            )

            request_id = "req_block_new_work"
            payload = {
                "target": "POWERSHELL5.1",
                "command": "Write-Output blocked",
            }
            request_syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "REQUEST_SYN",
                "request_id": request_id,
                "operation": "EXECUTION_V2_START",
                "payload": payload,
                "request_hash": sha256_payload(payload),
            }
            state.receive_request(request_syn)

            control = {
                "stage": "WRAP_UP_NOW",
                "action": "FINISH_RESPONSE_NORMALLY",
                "request_wrap_up": True,
                "manual_request": True,
                "directive": "checkpoint",
            }

            with patch(
                "adapter_server.codebridge_turn_control",
                return_value=control,
            ):
                response = state.response_syn(
                    request_id
                )

            result = response["payload"]
            self.assertFalse(
                result["operation_ok"]
            )
            self.assertEqual(
                result["error_type"],
                "TurnWrapUpRequested",
            )
            self.assertEqual(calls, [])
            self.assertEqual(
                result["turn_control"],
                control,
            )

    def test_wrap_up_allows_status_read(self):
        calls = []

        def status(payload, request_id=None):
            calls.append(request_id)
            return {
                "overall": "READY",
            }

        with tempfile.TemporaryDirectory() as tmp:
            state = AdapterState(
                ledger_path=Path(tmp) / "ledger.db",
                operations={
                    "STATUS": status,
                },
            )

            request_id = "req_allow_status"
            payload = {}
            request_syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "REQUEST_SYN",
                "request_id": request_id,
                "operation": "STATUS",
                "payload": payload,
                "request_hash": sha256_payload(payload),
            }
            state.receive_request(request_syn)

            control = {
                "stage": "WRAP_UP_NOW",
                "action": "FINISH_RESPONSE_NORMALLY",
                "request_wrap_up": True,
                "manual_request": True,
                "directive": "checkpoint",
            }

            with patch(
                "adapter_server.codebridge_turn_control",
                return_value=control,
            ):
                response = state.response_syn(
                    request_id
                )

            result = response["payload"]
            self.assertTrue(
                result["operation_ok"]
            )
            self.assertEqual(
                result["overall"],
                "READY",
            )
            self.assertEqual(
                calls,
                [request_id],
            )
            self.assertEqual(
                result["turn_control"],
                control,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
