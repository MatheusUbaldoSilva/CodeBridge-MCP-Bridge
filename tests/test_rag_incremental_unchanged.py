import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path

from rag.index.incremental import (
    SourceFileSnapshot,
    capture_source_file_snapshot,
    manifest_entry_content_unchanged,
    should_skip_file_reprocessing,
)
from rag.index.manifest import ManifestEntry, ManifestIndexKind


def entry_from_snapshot(snapshot, *, model_version="v1"):
    return ManifestEntry(
        project_id="codebridge",
        index_kind=ManifestIndexKind.TEXT,
        path=snapshot.path,
        size=snapshot.size,
        mtime_ns=snapshot.mtime_ns,
        sha256=snapshot.sha256,
        chunk_ids=("chunk-1",),
        model_version=model_version,
    )


class RagIncrementalUnchangedTests(unittest.TestCase):
    def test_snapshot_captures_path_size_mtime_and_sha(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "docs" / "readme.md"
            path.parent.mkdir()
            data = b"hello incremental\n"
            path.write_bytes(data)

            snapshot = capture_source_file_snapshot(
                root,
                "docs/readme.md",
            )

            self.assertEqual(snapshot.path, "docs/readme.md")
            self.assertEqual(snapshot.size, len(data))
            self.assertGreater(snapshot.mtime_ns, 0)
            self.assertEqual(
                snapshot.sha256,
                hashlib.sha256(data).hexdigest(),
            )

    def test_same_sha_skips_reprocessing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "file.txt"
            path.write_text("same", encoding="utf-8")
            snapshot = capture_source_file_snapshot(root, "file.txt")
            entry = entry_from_snapshot(snapshot)

            current = capture_source_file_snapshot(root, "file.txt")

            self.assertTrue(
                manifest_entry_content_unchanged(entry, current)
            )
            self.assertTrue(
                should_skip_file_reprocessing(entry, current)
            )

    def test_mtime_change_with_same_sha_still_skips(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "file.txt"
            path.write_text("same", encoding="utf-8")
            before = capture_source_file_snapshot(root, "file.txt")
            entry = entry_from_snapshot(before)

            changed_mtime = before.mtime_ns + 10_000_000
            os.utime(
                path,
                ns=(changed_mtime, changed_mtime),
            )
            after = capture_source_file_snapshot(root, "file.txt")

            self.assertNotEqual(before.mtime_ns, after.mtime_ns)
            self.assertEqual(before.sha256, after.sha256)
            self.assertTrue(
                should_skip_file_reprocessing(entry, after)
            )

    def test_content_change_does_not_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "file.txt"
            path.write_text("old", encoding="utf-8")
            before = capture_source_file_snapshot(root, "file.txt")
            entry = entry_from_snapshot(before)

            path.write_text("new", encoding="utf-8")
            after = capture_source_file_snapshot(root, "file.txt")

            self.assertNotEqual(before.sha256, after.sha256)
            self.assertFalse(
                should_skip_file_reprocessing(entry, after)
            )

    def test_path_mismatch_is_rejected(self):
        snapshot = SourceFileSnapshot(
            path="b.txt",
            size=1,
            mtime_ns=1,
            sha256="a" * 64,
        )
        entry = ManifestEntry(
            project_id="codebridge",
            index_kind=ManifestIndexKind.TEXT,
            path="a.txt",
            size=1,
            mtime_ns=1,
            sha256="a" * 64,
            chunk_ids=("chunk",),
            model_version="v1",
        )

        with self.assertRaises(ValueError):
            should_skip_file_reprocessing(entry, snapshot)

    def test_missing_file_snapshot_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                capture_source_file_snapshot(td, "missing.txt")

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                capture_source_file_snapshot(td, "../outside.txt")


if __name__ == "__main__":
    unittest.main()
