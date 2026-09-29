import json
import sys
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from chatgpt_companion import (
    COMPANION_HEADER,
    COMPANION_HEADER_VALUE,
    ChatGPTCompanionServer,
    ChatGPTTimerState,
)


class ExtensionHeartbeatStateTests(unittest.TestCase):
    def test_recorded_heartbeat_is_connected(self):
        server = ChatGPTCompanionServer(ChatGPTTimerState(), port=0)
        status = server.record_extension_heartbeat(
            {
                "version": "0.2.0",
                "extension_id": "abc123",
            }
        )

        self.assertTrue(status["connected"])
        self.assertEqual(status["version"], "0.2.0")
        self.assertEqual(status["extension_id"], "abc123")
        self.assertIsNotNone(status["age_seconds"])

    def test_old_heartbeat_becomes_disconnected(self):
        server = ChatGPTCompanionServer(ChatGPTTimerState(), port=0)
        server.record_extension_heartbeat(
            {
                "version": "0.2.0",
                "extension_id": "abc123",
            }
        )

        with server._extension_lock:
            server._extension_heartbeat["last_seen_epoch"] = (
                time.time() - 91.0
            )

        status = server.extension_status()
        self.assertFalse(status["connected"])
        self.assertGreaterEqual(status["age_seconds"], 90.0)


class ExtensionHeartbeatHttpTests(unittest.TestCase):
    def setUp(self):
        self.server = ChatGPTCompanionServer(
            ChatGPTTimerState(),
            host="127.0.0.1",
            port=0,
        )
        self.server.start()
        self.base = (
            "http://127.0.0.1:"
            + str(self.server.port)
        )

    def tearDown(self):
        self.server.stop()

    def _request(self, path, data=None, method="GET"):
        headers = {
            COMPANION_HEADER: COMPANION_HEADER_VALUE,
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            self.base + path,
            data=body,
            method=method,
            headers=headers,
        )
        with urlopen(request, timeout=2) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    def test_heartbeat_round_trip(self):
        posted = self._request(
            "/v1/extension/heartbeat",
            {
                "version": "0.2.0",
                "extension_id": "roundtrip-id",
            },
            method="POST",
        )

        self.assertTrue(posted["ok"])
        self.assertTrue(
            posted["extension"]["connected"]
        )

        status = self._request(
            "/v1/extension/status"
        )

        self.assertTrue(status["ok"])
        self.assertTrue(
            status["extension"]["connected"]
        )
        self.assertEqual(
            status["extension"]["version"],
            "0.2.0",
        )
        self.assertEqual(
            status["extension"]["extension_id"],
            "roundtrip-id",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
