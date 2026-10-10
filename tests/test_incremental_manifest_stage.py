"""Prove isolated manifest merge, replacement and failure safety."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind,
    load_index_manifest, save_index_manifest,
)
from rag.runtime.incremental_manifest_stage import (
    IncrementalManifestError, stage_incremental_manifest,
)


def entry(project, name, sha_seed):
    return ManifestEntry(
        project_id=project, index_kind=ManifestIndexKind.TEXT, path=name,
        size=42, mtime_ns=1, sha256=hashlib.sha256(sha_seed.encode()).hexdigest(),
        chunk_ids=(sha_seed,), model_version="test-model",
    )


class StageManifestTests(unittest.TestCase):
    def test_merge_preserves_other_projects(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, incoming, output = (root / n for n in ("old.json", "new.json", "merged.json"))
            save_index_manifest(original, IndexManifest((
                entry("a", "old.md", "old"), entry("b", "other.md", "other"),
            )))
            save_index_manifest(incoming, IndexManifest((
                entry("a", "old.md", "revised"), entry("a", "added.md", "added"),
            )))
            old_bytes, new_bytes = original.read_bytes(), incoming.read_bytes()
            result = stage_incremental_manifest(original, incoming, output, "a")
            self.assertEqual((result["added"], result["replaced"], result["total"]), (1, 1, 3))
            merged = load_index_manifest(output)
            self.assertEqual(merged.get("a", ManifestIndexKind.TEXT, "old.md").sha256,
                             entry("a", "old.md", "revised").sha256)
            self.assertIsNotNone(merged.get("b", ManifestIndexKind.TEXT, "other.md"))
            self.assertEqual((original.read_bytes(), incoming.read_bytes()), (old_bytes, new_bytes))

    def test_reject_other_project_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, incoming, output = (root / n for n in ("old.json", "new.json", "merged.json"))
            save_index_manifest(original, IndexManifest((entry("a", "old.md", "old"),)))
            save_index_manifest(incoming, IndexManifest((entry("b", "other.md", "new"),)))
            with self.assertRaises(IncrementalManifestError):
                stage_incremental_manifest(original, incoming, output, "a")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
