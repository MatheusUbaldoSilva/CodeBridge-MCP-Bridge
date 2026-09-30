# -*- coding: utf-8 -*-
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
if str(INSTALLER) not in sys.path:
    sys.path.insert(0, str(INSTALLER))

import updater


class FakeResponse:
    def __init__(self, payload):
        self._stream = io.BytesIO(payload)
        self.headers = {
            "Content-Length": str(len(payload)),
        }

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class UpdaterVersionTests(unittest.TestCase):
    def test_version_order(self):
        versions = [
            "2.0.1-prealpha",
            "2.0.1-alpha",
            "2.0.1-beta",
            "2.0.1-rc",
            "2.0.1",
            "2.0.2-prealpha",
        ]
        for left, right in zip(versions, versions[1:]):
            self.assertLess(
                updater.compare_versions(left, right),
                0,
            )
            self.assertGreater(
                updater.compare_versions(right, left),
                0,
            )

        self.assertEqual(
            updater.compare_versions(
                "2.0.1-prealpha",
                "2.0.1-prealpha",
            ),
            0,
        )

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValueError):
            updater.version_key("2.0")
        with self.assertRaises(ValueError):
            updater.version_key("2.0.1-preview")

    def test_current_version_skips_download(self):
        worker = updater.DownloadWorker()
        up_to_date = []
        finished = []
        failed = []
        progress = []

        worker.up_to_date.connect(up_to_date.append)
        worker.finished.connect(finished.append)
        worker.failed.connect(failed.append)
        worker.progress.connect(progress.append)

        release = {
            "commit_sha": "a" * 40,
            "version": updater.APP_VERSION,
            "dist_root": "https://example.invalid/dist",
        }
        with patch.object(
            updater,
            "resolve_remote_release",
            return_value=release,
        ):
            worker.run()

        self.assertEqual(
            up_to_date,
            [updater.APP_VERSION],
        )
        self.assertEqual(finished, [])
        self.assertEqual(failed, [])
        self.assertEqual(progress[-1], 100)

    def test_newer_version_downloads_and_checks_sha(self):
        worker = updater.DownloadWorker()
        finished = []
        failed = []
        statuses = []

        worker.finished.connect(finished.append)
        worker.failed.connect(failed.append)
        worker.status.connect(statuses.append)

        payload = b"CODEBRIDGE_TEST_INSTALLER"
        digest = hashlib.sha256(payload).hexdigest()
        release = {
            "commit_sha": "b" * 40,
            "version": "2.0.11-prealpha",
            "dist_root": "https://example.invalid/dist",
        }

        def fake_urlopen(request, timeout=0):
            url = request.full_url
            if url.endswith(".sha256"):
                return FakeResponse(
                    (digest + "  CodeBridge-Setup.exe\n").encode(
                        "ascii"
                    )
                )
            if url.endswith(".exe"):
                return FakeResponse(payload)
            raise AssertionError("URL inesperada: " + url)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                updater,
                "resolve_remote_release",
                return_value=release,
            ), patch.object(
                updater.urllib.request,
                "urlopen",
                side_effect=fake_urlopen,
            ), patch.object(
                updater.tempfile,
                "gettempdir",
                return_value=temp_dir,
            ):
                worker.run()

            self.assertEqual(failed, [])
            self.assertEqual(len(finished), 1)
            installer = Path(finished[0])
            self.assertEqual(
                installer.read_bytes(),
                payload,
            )

        self.assertTrue(
            any(
                "2.0.11-prealpha" in message
                for message in statuses
            )
        )


if __name__ == "__main__":
    unittest.main()
