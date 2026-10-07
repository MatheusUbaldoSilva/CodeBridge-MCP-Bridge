import unittest

from rag.index.incremental import (
    ExistingFileAction,
    SourceFileSnapshot,
    reconcile_existing_file,
)
from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
)


class Rag012IdempotentIndexingTests(unittest.TestCase):
    def make_entry(self):
        return ManifestEntry(
            project_id="codebridge",
            index_kind=ManifestIndexKind.CODE,
            path="src/main.py",
            size=10,
            mtime_ns=100,
            sha256="a" * 64,
            chunk_ids=("old-1",),
            model_version="code-v1",
        )

    def test_repeated_unchanged_pass_does_not_rechunk_or_reembed(self):
        entry = self.make_entry()
        manifest = IndexManifest(entries=(entry,))
        snapshot = SourceFileSnapshot(
            path=entry.path,
            size=entry.size,
            mtime_ns=999,
            sha256=entry.sha256,
        )
        calls = []

        first = reconcile_existing_file(
            manifest,
            entry,
            snapshot,
            current_model_version="code-v1",
            rechunk=lambda _: calls.append("rechunk"),
            reembed=lambda *_: calls.append("reembed"),
        )
        second = reconcile_existing_file(
            first.manifest,
            first.entry,
            snapshot,
            current_model_version="code-v1",
            rechunk=lambda _: calls.append("rechunk"),
            reembed=lambda *_: calls.append("reembed"),
        )

        self.assertEqual(first.action, ExistingFileAction.UNCHANGED)
        self.assertEqual(second.action, ExistingFileAction.UNCHANGED)
        self.assertEqual(first.manifest, manifest)
        self.assertEqual(second.manifest, manifest)
        self.assertEqual(calls, [])

    def test_changed_pass_runs_once_then_next_identical_pass_is_noop(self):
        entry = self.make_entry()
        manifest = IndexManifest(entries=(entry,))
        changed_snapshot = SourceFileSnapshot(
            path=entry.path,
            size=20,
            mtime_ns=200,
            sha256="b" * 64,
        )
        calls = []

        first = reconcile_existing_file(
            manifest,
            entry,
            changed_snapshot,
            current_model_version="code-v1",
            rechunk=lambda _: (
                calls.append("rechunk") or ("new-1",)
            ),
            reembed=lambda *_: calls.append("reembed"),
        )

        second = reconcile_existing_file(
            first.manifest,
            first.entry,
            changed_snapshot,
            current_model_version="code-v1",
            rechunk=lambda _: calls.append("rechunk-again"),
            reembed=lambda *_: calls.append("reembed-again"),
        )

        self.assertEqual(first.action, ExistingFileAction.REINDEXED)
        self.assertEqual(second.action, ExistingFileAction.UNCHANGED)
        self.assertEqual(calls, ["rechunk", "reembed"])
        self.assertEqual(
            first.entry.chunk_ids,
            ("new-1",),
        )
        self.assertEqual(first.entry.sha256, "b" * 64)
        self.assertEqual(
            second.manifest,
            first.manifest,
        )

    def test_model_version_mismatch_requires_prior_invalidation(self):
        entry = self.make_entry()
        manifest = IndexManifest(entries=(entry,))
        snapshot = SourceFileSnapshot(
            path=entry.path,
            size=entry.size,
            mtime_ns=entry.mtime_ns,
            sha256=entry.sha256,
        )
        calls = []

        with self.assertRaises(ValueError):
            reconcile_existing_file(
                manifest,
                entry,
                snapshot,
                current_model_version="code-v2",
                rechunk=lambda _: calls.append("rechunk"),
                reembed=lambda *_: calls.append("reembed"),
            )

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
