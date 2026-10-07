import tempfile
import unittest
from pathlib import Path

from rag.index.incremental import remove_missing_file
from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
)


class RagIncrementalRemovedFileTests(unittest.TestCase):
    def make_entry(
        self,
        *,
        path="src/removed.py",
        chunks=("chunk-1", "chunk-2"),
        project_id="codebridge",
        index_kind=ManifestIndexKind.CODE,
    ):
        return ManifestEntry(
            project_id=project_id,
            index_kind=index_kind,
            path=path,
            size=10,
            mtime_ns=100,
            sha256="a" * 64,
            chunk_ids=chunks,
            model_version="v1",
        )

    def test_missing_file_removes_manifest_entry_and_orphan_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            target = self.make_entry()
            keep = self.make_entry(
                path="src/keep.py",
                chunks=("keep-1",),
            )
            manifest = IndexManifest(entries=(target, keep))
            calls = []

            outcome = remove_missing_file(
                manifest,
                target,
                project_root=td,
                delete_chunks=lambda project, kind, chunks: calls.append(
                    (project, kind, chunks)
                ),
            )

            self.assertEqual(
                calls,
                [
                    (
                        "codebridge",
                        ManifestIndexKind.CODE,
                        ("chunk-1", "chunk-2"),
                    )
                ],
            )
            self.assertIsNone(
                outcome.manifest.get(
                    "codebridge",
                    ManifestIndexKind.CODE,
                    "src/removed.py",
                )
            )
            self.assertEqual(
                outcome.manifest.get(
                    "codebridge",
                    ManifestIndexKind.CODE,
                    "src/keep.py",
                ),
                keep,
            )
            self.assertEqual(
                outcome.removed_chunk_ids,
                ("chunk-1", "chunk-2"),
            )

    def test_existing_file_is_not_removed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "src" / "removed.py"
            path.parent.mkdir()
            path.write_text("still here", encoding="utf-8")
            target = self.make_entry()
            manifest = IndexManifest(entries=(target,))
            calls = []

            with self.assertRaises(ValueError):
                remove_missing_file(
                    manifest,
                    target,
                    project_root=root,
                    delete_chunks=lambda *args: calls.append(args),
                )

            self.assertEqual(calls, [])
            self.assertEqual(manifest.entries, (target,))

    def test_entry_must_match_manifest_state(self):
        with tempfile.TemporaryDirectory() as td:
            registered = self.make_entry(chunks=("old",))
            stale_copy = self.make_entry(chunks=("different",))
            manifest = IndexManifest(entries=(registered,))
            calls = []

            with self.assertRaises(ValueError):
                remove_missing_file(
                    manifest,
                    stale_copy,
                    project_root=td,
                    delete_chunks=lambda *args: calls.append(args),
                )

            self.assertEqual(calls, [])

    def test_empty_chunk_list_removes_entry_without_delete_callback(self):
        with tempfile.TemporaryDirectory() as td:
            target = self.make_entry(chunks=())
            manifest = IndexManifest(entries=(target,))
            calls = []

            outcome = remove_missing_file(
                manifest,
                target,
                project_root=td,
                delete_chunks=lambda *args: calls.append(args),
            )

            self.assertEqual(calls, [])
            self.assertEqual(outcome.removed_chunk_ids, ())
            self.assertEqual(outcome.manifest.entries, ())


if __name__ == "__main__":
    unittest.main()
