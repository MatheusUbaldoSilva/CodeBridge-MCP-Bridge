import unittest
from unittest.mock import patch

import runtime_client


class RuntimeClientReadBatchTests(unittest.TestCase):
    def test_read_batch_uses_single_endpoint(self):
        runtime = {
            "host": "127.0.0.1",
            "port": 9876,
            "token": "secret",
        }
        operations = [{"kind": "VERSION"}]
        with patch.object(
            runtime_client,
            "_load_runtime",
            return_value=runtime,
        ), patch.object(
            runtime_client,
            "_post_json",
            return_value={
                "batch": {
                    "count": 1,
                    "items": [],
                }
            },
        ) as post:
            result = runtime_client.codebridge_read_batch(
                operations
            )
        self.assertEqual(result["count"], 1)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            post.call_args.args[0],
            "http://127.0.0.1:9876/v1/read-only/batch",
        )
        self.assertEqual(
            post.call_args.args[2],
            {"operations": operations},
        )
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            30.0,
        )


if __name__ == "__main__":
    unittest.main()