import unittest
from unittest.mock import patch

import runtime_client


class RuntimeClientWaitTests(unittest.TestCase):
    def test_wait_uses_blocking_event_route_and_timeout_margin(self):
        runtime = {
            "host": "127.0.0.1",
            "port": 9876,
            "token": "secret",
        }
        response = {
            "output": {
                "execution_id": "e1",
                "state": "RUNNING",
                "timed_out": True,
            }
        }
        with patch.object(
            runtime_client,
            "_load_runtime",
            return_value=runtime,
        ), patch.object(
            runtime_client,
            "_get_json",
            return_value=response,
        ) as get_json:
            result = runtime_client.codebridge_v2_wait(
                "e1",
                cursor=17,
                max_chars=4096,
                timeout_ms=2500,
            )

        self.assertEqual(result["execution_id"], "e1")
        url = get_json.call_args.args[0]
        self.assertIn(
            "/v1/phase5f/executions/e1/wait?",
            url,
        )
        self.assertIn("cursor=17", url)
        self.assertIn("max_chars=4096", url)
        self.assertIn("timeout_ms=2500", url)
        self.assertEqual(
            get_json.call_args.kwargs["timeout"],
            7.5,
        )

    def test_wait_timeout_is_clamped(self):
        runtime = {
            "host": "127.0.0.1",
            "port": 9876,
            "token": "secret",
        }
        with patch.object(
            runtime_client,
            "_load_runtime",
            return_value=runtime,
        ), patch.object(
            runtime_client,
            "_get_json",
            return_value={"output": {}},
        ) as get_json:
            runtime_client.codebridge_v2_wait(
                "e2",
                timeout_ms=999999,
            )
        url = get_json.call_args.args[0]
        self.assertIn("timeout_ms=120000", url)
        self.assertEqual(
            get_json.call_args.kwargs["timeout"],
            125.0,
        )


if __name__ == "__main__":
    unittest.main()
