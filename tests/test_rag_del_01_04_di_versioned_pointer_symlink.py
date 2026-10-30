"""RAG-DEL-01.04-DI: generation reader rejects redirected pointer, scratch only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from rag.runtime.production_generation_read import (
    _read_pointer, production_generation_read,
)


class ProductionReaderRedirectTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "CodeBridge" / "rag"
        generation = self.state / "generations" / "testgen"
        generation.mkdir(parents=True)
        (generation / "rag_index.sqlite3").write_bytes(b"synthetic-index")
        (generation / "qdrant").mkdir()
        (generation / "rag-index-manifest.json").write_text(
            "{}", encoding="utf-8",
        )
        self.pointer = self.state / "active-generation.json"
        self.pointer.write_text(
            json.dumps({"schema_version": 1, "generation": "testgen"}),
            encoding="utf-8",
        )

    def read_locked(self):
        with (
            patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                  return_value=self.state / "rag_index.sqlite3"),
            patch("rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                  return_value=self.state / "rag_index.sqlite3"),
        ):
            with production_generation_read() as paths:
                return paths

    def test_regular_generation_pointer_still_reads(self):
        result = self.read_locked()
        self.assertEqual(result.generation, "testgen")
        self.assertEqual(result.sqlite.name, "rag_index.sqlite3")
        self.assertTrue((self.state / "production-generation.lock").is_file())

    def test_fake_redirect_detection_rejects_before_following_pointer(self):
        with patch.object(
            Path, "is_symlink", autospec=True,
            side_effect=lambda path: path == self.pointer,
        ):
            with self.assertRaisesRegex(RuntimeError, "redirected"):
                _read_pointer(self.state)
            with self.assertRaisesRegex(RuntimeError, "redirected"):
                self.read_locked()
        # Failed reader must have released generation lock.
        self.assertEqual(self.read_locked().generation, "testgen")

    def test_actual_redirect_to_external_file_is_rejected_when_supported(self):
        external = self.root / "external-pointer.json"
        external.write_bytes(self.pointer.read_bytes())
        self.pointer.unlink()
        try:
            self.pointer.symlink_to(external)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Windows symlink creation not permitted: " + str(exc))
        self.assertTrue(self.pointer.is_symlink())
        with self.assertRaisesRegex(RuntimeError, "redirected"):
            self.read_locked()
        self.pointer.unlink()
        self.pointer.write_text(
            json.dumps({"schema_version": 1, "generation": "testgen"}),
            encoding="utf-8",
        )
        self.assertEqual(self.read_locked().generation, "testgen")