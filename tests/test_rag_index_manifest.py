import json
import tempfile
import unittest
from pathlib import Path

from rag.index.manifest import (
    DEFAULT_MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    IndexManifest,
    ManifestEntry,
    ManifestError,
    ManifestIndexKind,
    load_index_manifest,
    manifest_entry_key,
    save_index_manifest,
)


class RagIndexManifestTests(unittest.TestCase):
    def entry(
        self,
        *,
        project_id="codebridge",
        index_kind=ManifestIndexKind.TEXT,
        path="docs/readme.md",
        size=123,
        mtime_ns=1000,
        sha256="a" * 64,
        chunk_ids=("chunk-1", "chunk-2"),
        model_version="model-revision-1",
    ):
        return ManifestEntry(
            project_id=project_id,
            index_kind=index_kind,
            path=path,
            size=size,
            mtime_ns=mtime_ns,
            sha256=sha256,
            chunk_ids=chunk_ids,
            model_version=model_version,
        )

    def test_required_fields_are_preserved(self):
        entry = self.entry()
        data = entry.to_dict()

        self.assertEqual(data["path"], "docs/readme.md")
        self.assertEqual(data["size"], 123)
        self.assertEqual(data["mtime_ns"], 1000)
        self.assertEqual(data["sha256"], "a" * 64)
        self.assertEqual(
            data["chunk_ids"],
            ["chunk-1", "chunk-2"],
        )
        self.assertEqual(
            data["model_version"],
            "model-revision-1",
        )

    def test_path_is_canonical(self):
        entry = self.entry(path=r".\docs\readme.md")
        self.assertEqual(entry.path, "docs/readme.md")

    def test_manifest_key_is_deterministic_and_scoped(self):
        first = manifest_entry_key(
            "codebridge",
            ManifestIndexKind.TEXT,
            "docs/readme.md",
        )
        second = manifest_entry_key(
            "codebridge",
            ManifestIndexKind.TEXT,
            r"docs\readme.md",
        )
        other_space = manifest_entry_key(
            "codebridge",
            ManifestIndexKind.CODE,
            "docs/readme.md",
        )
        other_project = manifest_entry_key(
            "drones",
            ManifestIndexKind.TEXT,
            "docs/readme.md",
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, other_space)
        self.assertNotEqual(first, other_project)

    def test_upsert_replaces_same_logical_entry(self):
        original = self.entry(model_version="v1")
        updated = self.entry(
            model_version="v2",
            sha256="b" * 64,
            chunk_ids=("chunk-3",),
        )

        manifest = IndexManifest(
            entries=(original,)
        ).upsert(updated)

        self.assertEqual(len(manifest.entries), 1)
        loaded = manifest.get(
            "codebridge",
            ManifestIndexKind.TEXT,
            "docs/readme.md",
        )
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.model_version, "v2")
        self.assertEqual(loaded.sha256, "b" * 64)
        self.assertEqual(loaded.chunk_ids, ("chunk-3",))

    def test_remove_only_target_entry(self):
        text = self.entry()
        code = self.entry(
            index_kind=ManifestIndexKind.CODE,
            model_version="code-v1",
        )
        manifest = IndexManifest(
            entries=(text, code)
        )

        removed = manifest.remove(
            "codebridge",
            ManifestIndexKind.TEXT,
            "docs/readme.md",
        )

        self.assertIsNone(
            removed.get(
                "codebridge",
                ManifestIndexKind.TEXT,
                "docs/readme.md",
            )
        )
        self.assertIsNotNone(
            removed.get(
                "codebridge",
                ManifestIndexKind.CODE,
                "docs/readme.md",
            )
        )

    def test_missing_manifest_loads_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / DEFAULT_MANIFEST_FILENAME
            manifest = load_index_manifest(path)
            self.assertEqual(manifest.entries, ())

    def test_round_trip_persists_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state" / DEFAULT_MANIFEST_FILENAME
            manifest = IndexManifest(
                entries=(
                    self.entry(),
                    self.entry(
                        project_id="new-world-pvp",
                        index_kind=ManifestIndexKind.CODE,
                        path="src/game.cpp",
                        size=456,
                        mtime_ns=2000,
                        sha256="b" * 64,
                        chunk_ids=("code-1",),
                        model_version="jina-code-revision",
                    ),
                )
            )

            save_index_manifest(path, manifest)
            loaded = load_index_manifest(path)

            self.assertEqual(loaded, manifest)
            self.assertTrue(path.is_file())

    def test_saved_json_is_deterministic_and_versioned(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            manifest = IndexManifest(
                entries=(
                    self.entry(
                        project_id="drones",
                        path="z.md",
                    ),
                    self.entry(
                        path="a.md",
                    ),
                )
            )

            save_index_manifest(path, manifest)
            first = path.read_text(encoding="utf-8")
            save_index_manifest(path, manifest)
            second = path.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            payload = json.loads(first)
            self.assertEqual(
                payload["schema_version"],
                MANIFEST_SCHEMA_VERSION,
            )
            self.assertEqual(len(payload["entries"]), 2)

    def test_invalid_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 999,
                        "entries": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ManifestError):
                load_index_manifest(path)

    def test_duplicate_logical_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            IndexManifest(
                entries=(
                    self.entry(model_version="v1"),
                    self.entry(model_version="v2"),
                )
            )

    def test_invalid_required_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.entry(size=-1)
        with self.assertRaises(ValueError):
            self.entry(mtime_ns=-1)
        with self.assertRaises(ValueError):
            self.entry(sha256="bad")
        with self.assertRaises(ValueError):
            self.entry(chunk_ids=("x", "x"))
        with self.assertRaises(ValueError):
            self.entry(model_version=" ")
        with self.assertRaises(ValueError):
            self.entry(path="../escape.md")


if __name__ == "__main__":
    unittest.main()
