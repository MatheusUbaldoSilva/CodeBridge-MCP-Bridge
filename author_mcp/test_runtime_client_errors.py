import unittest
from unittest.mock import patch

import runtime_client


class RuntimeClientErrorTests(unittest.TestCase):
    def test_http_400_is_request_error_not_unavailable(self):
        error = runtime_client.HTTPPoolResponseError(
            400,
            "Bad Request",
            '{"ok":false,"error":"RuntimeError","message":"terminal ocupado"}',
        )
        with patch.object(
            runtime_client.SHARED_HTTP_POOL,
            "request_json",
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

    def test_transport_error_is_unavailable_and_not_retried(self):
        error = runtime_client.HTTPPoolTransportError(
            "connection refused"
        )
        with patch.object(
            runtime_client.SHARED_HTTP_POOL,
            "request_json",
            side_effect=error,
        ) as request:
            with self.assertRaises(
                runtime_client.CodeBridgeUnavailable
            ):
                runtime_client._post_json(
                    "http://127.0.0.1/test",
                    "token",
                    {"x": 1},
                )
        self.assertEqual(request.call_count, 1)

    def test_invalid_json_is_request_error_not_transport(self):
        error = runtime_client.HTTPPoolDecodeError(
            "resposta JSON invalida"
        )
        with patch.object(
            runtime_client.SHARED_HTTP_POOL,
            "request_json",
            side_effect=error,
        ):
            with self.assertRaises(
                runtime_client.CodeBridgeRequestError
            ):
                runtime_client._get_json(
                    "http://127.0.0.1/test",
                    "token",
                )

    def test_get_transport_error_is_unavailable(self):
        error = runtime_client.HTTPPoolTransportError(
            "connection refused"
        )
        with patch.object(
            runtime_client.SHARED_HTTP_POOL,
            "request_json",
            side_effect=error,
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