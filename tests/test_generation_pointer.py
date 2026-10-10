import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_pointer import resolve_generation, RagGenerationPointerError


class PointerTests(unittest.TestCase):
    def test_missing_pointer_preserves_legacy(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(resolve_generation(temp))

    def test_valid_generation_keeps_three_paths_together(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generation = root / "generations" / "gen-001"
            (generation / "qdrant").mkdir(parents=True)
            (generation / "rag_index.sqlite3").write_bytes(b"fixture")
            (generation / "rag-index-manifest.json").write_text("{}")
            (root / "active-generation.json").write_text(json.dumps({
                "schema_version": 1, "generation": "gen-001"}))
            paths = resolve_generation(root)
            self.assertEqual(paths.generation, "gen-001")
            self.assertEqual(paths.sqlite.parent, paths.qdrant.parent)
            self.assertEqual(paths.sqlite.parent, paths.manifest.parent)

    def test_rejects_traversal_and_incomplete_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "active-generation.json"
            pointer.write_text('{"schema_version":1,"generation":"../other"}')
            with self.assertRaises(RagGenerationPointerError):
                resolve_generation(root)
            pointer.write_text('{"schema_version":1,"generation":"missing"}')
            with self.assertRaises(RagGenerationPointerError):
                resolve_generation(root)

    def test_rejects_broken_json(self):
        with tempfile.TemporaryDirectory() as temp:
            pointer = Path(temp) / "active-generation.json"
            pointer.write_text("{oops")
            with self.assertRaises(RagGenerationPointerError):
                resolve_generation(temp)
