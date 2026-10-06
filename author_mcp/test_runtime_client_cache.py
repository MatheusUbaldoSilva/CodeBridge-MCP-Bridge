import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_client


class RuntimeDescriptorCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime_file = Path(self.temp.name) / "runtime.json"
        self.original_runtime_file = runtime_client.RUNTIME_FILE
        runtime_client.RUNTIME_FILE = self.runtime_file
        runtime_client._invalidate_runtime_cache()

    def tearDown(self):
        runtime_client.RUNTIME_FILE = self.original_runtime_file
        runtime_client._invalidate_runtime_cache()
        self.temp.cleanup()

    def write_runtime(self, *, port=1111, token="token-a", pad=""):
        self.runtime_file.write_text(
            json.dumps({
                "host": "127.0.0.1",
                "port": port,
                "token": token,
                "pad": pad,
            }),
            encoding="utf-8",
        )

    def test_unchanged_file_is_parsed_once(self):
        self.write_runtime()
        original = runtime_client._read_runtime_file
        with patch.object(
            runtime_client,
            "_read_runtime_file",
            wraps=original,
        ) as reader:
            first = runtime_client._load_runtime()
            second = runtime_client._load_runtime()
        self.assertEqual(first, second)
        self.assertEqual(reader.call_count, 1)
        self.assertIsNot(first, second)

    def test_file_change_invalidates_immediately(self):
        self.write_runtime(port=1111, token="token-a")
        first = runtime_client._load_runtime()
        self.write_runtime(
            port=2222,
            token="token-b",
            pad="signature-change",
        )
        second = runtime_client._load_runtime()
        self.assertEqual(first["port"], 1111)
        self.assertEqual(second["port"], 2222)
        self.assertEqual(second["token"], "token-b")

    def test_deleted_runtime_never_serves_stale_cache(self):
        self.write_runtime()
        runtime_client._load_runtime()
        self.runtime_file.unlink()
        with self.assertRaises(
            runtime_client.CodeBridgeUnavailable
        ):
            runtime_client._load_runtime()


if __name__ == "__main__":
    unittest.main()