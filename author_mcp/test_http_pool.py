import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from http_pool import (
    HTTPPoolResponseError,
    JSONHTTPConnectionPool,
)


class KeepAliveHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    ports = set()
    lock = threading.RLock()

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload, *, close=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if close:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with self.lock:
            self.ports.add(self.client_address[1])
        if self.path == "/error":
            return self._send(
                409, {"ok": False, "message": "conflict"}
            )
        return self._send(
            200,
            {"ok": True, "path": self.path},
            close=self.path == "/close",
        )


class HTTPPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        KeepAliveHandler.ports = set()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            KeepAliveHandler,
        )
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        KeepAliveHandler.ports = set()
        self.pool = JSONHTTPConnectionPool(
            max_idle_per_origin=2,
            max_idle_seconds=30,
        )

    def tearDown(self):
        self.pool.close_all()

    def test_sequential_requests_reuse_one_socket(self):
        for index in range(12):
            result = self.pool.request_json(
                "GET",
                self.base + f"/ok?i={index}",
                timeout=2,
            )
            self.assertTrue(result["ok"])
        stats = self.pool.stats()
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["reused"], 11)
        self.assertEqual(stats["requests"], 12)
        self.assertEqual(len(KeepAliveHandler.ports), 1)

    def test_connection_close_is_not_reused(self):
        self.pool.request_json(
            "GET", self.base + "/close", timeout=2
        )
        self.pool.request_json(
            "GET", self.base + "/after", timeout=2
        )
        stats = self.pool.stats()
        self.assertEqual(stats["created"], 2)
        self.assertGreaterEqual(stats["discarded"], 1)

    def test_http_error_keeps_structured_status(self):
        with self.assertRaises(
            HTTPPoolResponseError
        ) as ctx:
            self.pool.request_json(
                "GET", self.base + "/error", timeout=2
            )
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn("conflict", ctx.exception.body)


if __name__ == "__main__":
    unittest.main()