from contextlib import nullcontext
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime import production_generation_read as reader
from rag.runtime import production_generation_transition as writer


class ProductionReaderFailClosedIsolatedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codebridge-p3-isolated-")
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "CodeBridge" / "rag"
        self.state.mkdir(parents=True)
        (self.state / "rag_index.sqlite3").write_bytes(b"test-fixture")
        (self.state / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
        (self.state / "qdrant").mkdir()
        self.candidate = "v1_delta_abc123ef"
        self.bundle = self.state / "generations" / self.candidate
        self.bundle.mkdir(parents=True)
        self.bundle.joinpath("rag_index.sqlite3").write_bytes(b"candidate")
        self.bundle.joinpath("rag-index-manifest.json").write_text("{}", encoding="utf-8")
        self.bundle.joinpath("qdrant").mkdir()

    def _patched_reader(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(reader, "production_generation_lock", side_effect=lambda **_: nullcontext()))
        stack.enter_context(patch.object(reader, "resolve_rag_sqlite_path", return_value=self.state / "rag_index.sqlite3"))
        stack.enter_context(patch.object(reader, "resolve_rag_manifest_path", return_value=self.state / "rag-index-manifest.json"))
        stack.enter_context(patch.object(reader, "resolve_qdrant_local_path", return_value=self.state / "qdrant"))
        return stack

    def test_legacy_and_candidate_reader_paths_are_separate(self):
        with self._patched_reader():
            with reader.production_generation_read() as active:
                self.assertEqual(active.generation, "legacy")
                self.assertEqual(active.sqlite, self.state / "rag_index.sqlite3")
            writer._atomic_json(self.state / writer.POINTER_NAME, {
                "schema_version": 1, "generation": self.candidate})
            with reader.production_generation_read() as active:
                self.assertEqual(active.generation, self.candidate)
                self.assertEqual(active.sqlite, self.bundle / "rag_index.sqlite3")

    def test_pending_journal_blocks_both_pointer_states(self):
        journal={"schema_version": 1, "state": "PREPARED", "previous": "legacy", "candidate": self.candidate}
        with self._patched_reader():
            writer._atomic_json(self.state / writer.JOURNAL_NAME, journal)
            with self.assertRaisesRegex(RuntimeError, "recovery required"):
                with reader.production_generation_read():
                    pass
            writer._atomic_json(self.state / writer.POINTER_NAME, {
                "schema_version": 1, "generation": self.candidate})
            with self.assertRaisesRegex(RuntimeError, "recovery required"):
                with reader.production_generation_read():
                    pass

    def test_incomplete_candidate_and_corrupt_pointer_fail_closed(self):
        with self._patched_reader():
            writer._atomic_json(self.state / writer.POINTER_NAME, {
                "schema_version": 1, "generation": self.candidate})
            (self.bundle / "rag-index-manifest.json").unlink()
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                with reader.production_generation_read():
                    pass
            (self.state / writer.POINTER_NAME).write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                with reader.production_generation_read():
                    pass

    def test_pending_rollback_preserves_legacy_and_candidate(self):
        journal={"schema_version": 1, "state": "PREPARED", "previous": "legacy", "candidate": self.candidate}
        writer._atomic_json(self.state / writer.JOURNAL_NAME, journal)
        writer._atomic_json(self.state / writer.POINTER_NAME, {
            "schema_version": 1, "generation": self.candidate})
        with patch.object(writer, "_root", return_value=self.state), patch.object(
                writer, "production_generation_lock", side_effect=lambda **_: nullcontext()):
            report=writer.rollback_pending_to_legacy(expected_candidate=self.candidate)
        self.assertEqual(report["state"], "RECOVERED_LEGACY")
        self.assertTrue((self.state / "rag_index.sqlite3").is_file())
        self.assertTrue((self.bundle / "rag_index.sqlite3").is_file())
        self.assertFalse((self.state / writer.JOURNAL_NAME).exists())
        with self._patched_reader():
            with reader.production_generation_read() as active:
                self.assertEqual(active.generation, "legacy")
