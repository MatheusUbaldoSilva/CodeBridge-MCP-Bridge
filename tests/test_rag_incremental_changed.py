import unittest

from rag.index.incremental import (
    SourceFileSnapshot,
    reindex_changed_file,
)
from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
)


class RagIncrementalChangedFileTests(unittest.TestCase):
    def make_entry(
        self,
        *,
        path="src/a.py",
        sha="a" * 64,
        chunks=("old-1", "old-2"),
        model_version="v1",
        project_id="codebridge",
    ):
        return ManifestEntry(
            project_id=project_id,
            index_kind=ManifestIndexKind.CODE,
            path=path,
            size=10,
            mtime_ns=100,
            sha256=sha,
            chunk_ids=chunks,
            model_version=model_version,
        )

    def test_changed_file_rechunks_and_reembeds_only_target(self):
        target = self.make_entry(path="src/a.py")
        untouched = self.make_entry(
            path="src/b.py",
            sha="b" * 64,
            chunks=("b-1",),
        )
        manifest = IndexManifest(entries=(target, untouched))
        snapshot = SourceFileSnapshot(
            path="src/a.py",
            size=20,
            mtime_ns=200,
            sha256="c" * 64,
        )
        calls = []

        def rechunk(current):
            calls.append(("rechunk", current.path))
            return ("new-1", "new-2")

        def reembed(current, chunk_ids, index_kind, model_version):
            calls.append(
                (
                    "reembed",
                    current.path,
                    chunk_ids,
                    index_kind,
                    model_version,
                )
            )

        outcome = reindex_changed_file(
            manifest,
            target,
            snapshot,
            model_version="v2",
            rechunk=rechunk,
            reembed=reembed,
        )

        self.assertEqual(
            calls,
            [
                ("rechunk", "src/a.py"),
                (
                    "reembed",
                    "src/a.py",
                    ("new-1", "new-2"),
                    ManifestIndexKind.CODE,
                    "v2",
                ),
            ],
        )
        updated = outcome.manifest.get(
            "codebridge",
            ManifestIndexKind.CODE,
            "src/a.py",
        )
        preserved = outcome.manifest.get(
            "codebridge",
            ManifestIndexKind.CODE,
            "src/b.py",
        )

        self.assertIsNotNone(updated)
        self.assertIsNotNone(preserved)
        assert updated is not None
        assert preserved is not None

        self.assertEqual(updated.sha256, "c" * 64)
        self.assertEqual(updated.chunk_ids, ("new-1", "new-2"))
        self.assertEqual(updated.model_version, "v2")
        self.assertEqual(preserved, untouched)
        self.assertEqual(
            outcome.retired_chunk_ids,
            ("old-1", "old-2"),
        )

    def test_retired_chunks_only_include_removed_old_ids(self):
        target = self.make_entry(
            chunks=("keep", "remove"),
        )
        manifest = IndexManifest(entries=(target,))
        snapshot = SourceFileSnapshot(
            path="src/a.py",
            size=30,
            mtime_ns=300,
            sha256="d" * 64,
        )

        outcome = reindex_changed_file(
            manifest,
            target,
            snapshot,
            model_version="v2",
            rechunk=lambda _: ("keep", "new"),
            reembed=lambda *_: None,
        )

        self.assertEqual(
            outcome.retired_chunk_ids,
            ("remove",),
        )

    def test_unchanged_file_is_rejected_before_callbacks(self):
        target = self.make_entry()
        manifest = IndexManifest(entries=(target,))
        snapshot = SourceFileSnapshot(
            path=target.path,
            size=target.size,
            mtime_ns=999,
            sha256=target.sha256,
        )
        calls = []

        with self.assertRaises(ValueError):
            reindex_changed_file(
                manifest,
                target,
                snapshot,
                model_version="v1",
                rechunk=lambda _: calls.append("rechunk"),
                reembed=lambda *_: calls.append("reembed"),
            )

        self.assertEqual(calls, [])

    def test_path_mismatch_is_rejected_before_callbacks(self):
        target = self.make_entry(path="src/a.py")
        manifest = IndexManifest(entries=(target,))
        snapshot = SourceFileSnapshot(
            path="src/b.py",
            size=20,
            mtime_ns=200,
            sha256="c" * 64,
        )
        calls = []

        with self.assertRaises(ValueError):
            reindex_changed_file(
                manifest,
                target,
                snapshot,
                model_version="v2",
                rechunk=lambda _: calls.append("rechunk"),
                reembed=lambda *_: calls.append("reembed"),
            )

        self.assertEqual(calls, [])

    def test_duplicate_chunk_ids_from_rechunk_are_rejected(self):
        target = self.make_entry()
        manifest = IndexManifest(entries=(target,))
        snapshot = SourceFileSnapshot(
            path=target.path,
            size=20,
            mtime_ns=200,
            sha256="c" * 64,
        )
        embedded = []

        with self.assertRaises(ValueError):
            reindex_changed_file(
                manifest,
                target,
                snapshot,
                model_version="v2",
                rechunk=lambda _: ("dup", "dup"),
                reembed=lambda *_: embedded.append(True),
            )

        self.assertEqual(embedded, [])


if __name__ == "__main__":
    unittest.main()
