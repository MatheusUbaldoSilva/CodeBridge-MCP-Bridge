import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import runtime_client


class RuntimeClientErrorTests(unittest.TestCase):
    def test_http_400_is_request_error_not_unavailable(self):
        body = io.BytesIO(
            b'{"ok":false,"error":"RuntimeError","message":"terminal ocupado"}'
        )
        error = HTTPError(
            "http://127.0.0.1/test",
            400,
            "Bad Request",
            hdrs=None,
            fp=body,
        )
        with patch.object(
            runtime_client,
            "urlopen",
            side_effect=error,
        ):
            with self.assertRaises(
                runtime_client.CodeBridgeRequestError
            ) as ctx:
                runtime_client._post_json(
                    "http://127.0.0.1/test",
                    "token",
                    {"x": 1},
                )
        self.assertIn("HTTP 400", str(ctx.exception))
        self.assertIn("terminal ocupado", str(ctx.exception))

    def test_url_error_is_unavailable(self):
        with patch.object(
            runtime_client,
            "urlopen",
            side_effect=URLError("connection refused"),
        ):
            with self.assertRaises(
                runtime_client.CodeBridgeUnavailable
            ):
                runtime_client._get_json(
                    "http://127.0.0.1/test",
                    "token",
                )


if __name__ == "__main__":
    unittest.main()