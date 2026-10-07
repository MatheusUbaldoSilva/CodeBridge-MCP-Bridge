import unittest

from rag.index.incremental import invalidate_model_version
from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
)


class RagIncrementalModelVersionTests(unittest.TestCase):
    def make_entry(
        self,
        *,
        project_id="codebridge",
        index_kind=ManifestIndexKind.TEXT,
        path="docs/readme.md",
        model_version="v1",
        chunks=("chunk-1",),
    ):
        return ManifestEntry(
            project_id=project_id,
            index_kind=index_kind,
            path=path,
            size=10,
            mtime_ns=100,
            sha256="a" * 64,
            chunk_ids=chunks,
            model_version=model_version,
        )

    def test_code_model_change_invalidates_only_code_space(self):
        text_entry = self.make_entry(
            index_kind=ManifestIndexKind.TEXT,
            path="docs/readme.md",
            model_version="text-v1",
            chunks=("text-1",),
        )
        code_entry = self.make_entry(
            index_kind=ManifestIndexKind.CODE,
            path="src/main.py",
            model_version="code-v1",
            chunks=("code-1", "code-2"),
        )
        manifest = IndexManifest(
            entries=(text_entry, code_entry)
        )
        calls = []

        outcome = invalidate_model_version(
            manifest,
            project_id="codebridge",
            index_kind=ManifestIndexKind.CODE,
            current_model_version="code-v2",
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
                    ("code-1", "code-2"),
                )
            ],
        )
        self.assertEqual(
            outcome.invalidated_entries,
            (code_entry,),
        )
        self.assertEqual(
            outcome.removed_chunk_ids,
            ("code-1", "code-2"),
        )
        self.assertIsNotNone(
            outcome.manifest.get(
                "codebridge",
                ManifestIndexKind.TEXT,
                "docs/readme.md",
            )
        )
        self.assertIsNone(
            outcome.manifest.get(
                "codebridge",
                ManifestIndexKind.CODE,
                "src/main.py",
            )
        )

    def test_text_model_change_preserves_code_space(self):
        text_entry = self.make_entry(
            index_kind=ManifestIndexKind.TEXT,
            model_version="text-v1",
        )
        code_entry = self.make_entry(
            index_kind=ManifestIndexKind.CODE,
            path="src/main.py",
            model_version="code-v1",
        )
        manifest = IndexManifest(
            entries=(text_entry, code_entry)
        )

        outcome = invalidate_model_version(
            manifest,
            project_id="codebridge",
            index_kind=ManifestIndexKind.TEXT,
            current_model_version="text-v2",
            delete_chunks=lambda *_: None,
        )

        self.assertIsNone(
            outcome.manifest.get(
                "codebridge",
                ManifestIndexKind.TEXT,
                "docs/readme.md",
            )
        )
        self.assertEqual(
            outcome.manifest.get(
                "codebridge",
                ManifestIndexKind.CODE,
                "src/main.py",
            ),
            code_entry,
        )

    def test_same_model_version_invalidates_nothing(self):
        entry = self.make_entry(
            model_version="text-v2",
        )
        manifest = IndexManifest(entries=(entry,))
        calls = []

        outcome = invalidate_model_version(
            manifest,
            project_id="codebridge",
            index_kind=ManifestIndexKind.TEXT,
            current_model_version="text-v2",
            delete_chunks=lambda *args: calls.append(args),
        )

        self.assertEqual(outcome.manifest, manifest)
        self.assertEqual(outcome.invalidated_entries, ())
        self.assertEqual(outcome.removed_chunk_ids, ())
        self.assertEqual(calls, [])

    def test_other_project_is_not_invalidated(self):
        target = self.make_entry(
            project_id="codebridge",
            model_version="v1",
        )
        other = self.make_entry(
            project_id="drones",
            path="docs/drone.md",
            model_version="v1",
            chunks=("drone-1",),
        )
        manifest = IndexManifest(entries=(target, other))

        outcome = invalidate_model_version(
            manifest,
            project_id="codebridge",
            index_kind=ManifestIndexKind.TEXT,
            current_model_version="v2",
            delete_chunks=lambda *_: None,
        )

        self.assertIsNone(
            outcome.manifest.get(
                "codebridge",
                ManifestIndexKind.TEXT,
                "docs/readme.md",
            )
        )
        self.assertEqual(
            outcome.manifest.get(
                "drones",
                ManifestIndexKind.TEXT,
                "docs/drone.md",
            ),
            other,
        )

    def test_invalid_current_model_version_is_rejected(self):
        manifest = IndexManifest()

        with self.assertRaises(ValueError):
            invalidate_model_version(
                manifest,
                project_id="codebridge",
                index_kind=ManifestIndexKind.TEXT,
                current_model_version=" ",
                delete_chunks=lambda *_: None,
            )


if __name__ == "__main__":
    unittest.main()
