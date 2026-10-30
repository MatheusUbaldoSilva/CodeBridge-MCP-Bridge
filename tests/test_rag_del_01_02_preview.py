"""Isolated read-only tests for RAG-DEL-01.02."""
from pathlib import Path
from contextlib import closing
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sqlite3

from rag.runtime.knowledge_deletion_preview import (
    KnowledgeDeletionPreviewError, preview_knowledge_removal,
)

MODULE = "rag.runtime.knowledge_deletion_preview.resolve_isolated_project"


class KnowledgeDeletionPreviewTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "private.sqlite3"
        with closing(sqlite3.connect(self.db)) as cn:
            cn.executescript("""
                CREATE TABLE rag_documents(project_id TEXT,path TEXT);
                CREATE TABLE rag_chunks(project_id TEXT,path TEXT);
                INSERT INTO rag_documents VALUES('demo','a.cpp');
                INSERT INTO rag_documents VALUES('demo','b.md');
                INSERT INTO rag_documents VALUES('other','a.cpp');
                INSERT INTO rag_chunks VALUES('demo','a.cpp');
                INSERT INTO rag_chunks VALUES('demo','a.cpp');
                INSERT INTO rag_chunks VALUES('demo','b.md');
                INSERT INTO rag_chunks VALUES('other','a.cpp');
            """)
        self.mock = patch(
            MODULE, return_value=SimpleNamespace(
                sqlite=self.db, manifest=self.root / "manifest.json", generation="auto_test",
                source_revision="f" * 64,
            )
        )
        self.mock.start()
        self.addCleanup(self.mock.stop)
        (self.root / "manifest.json").write_text("fixture", encoding="utf-8")
        self.entries = [
            SimpleNamespace(project_id="demo", path="a.cpp", chunk_ids=("a1", "a2")),
            SimpleNamespace(project_id="demo", path="b.md", chunk_ids=("b1",)),
        ]
        manifest_patch = patch(
            "rag.runtime.knowledge_deletion_preview.load_index_manifest",
            return_value=SimpleNamespace(entries=self.entries),
        )
        manifest_patch.start()
        self.addCleanup(manifest_patch.stop)

    def test_selected_and_preserved_counts_deterministic(self):
        before = self.db.read_bytes()
        first = preview_knowledge_removal("demo", ["b.md", "a.cpp"])
        second = preview_knowledge_removal("demo", ["a.cpp", "b.md"])
        self.assertEqual(first, second)
        self.assertEqual(first["documents_to_remove"], 2)
        self.assertEqual(first["chunks_to_remove"], 3)
        self.assertEqual(first["chunks_to_preserve"], 0)
        self.assertFalse(first["deletion_authorized"])
        self.assertFalse(first["source_files_modified"])
        self.assertEqual(before, self.db.read_bytes())

    def test_partial_selection_preserves_other_files(self):
        item = preview_knowledge_removal("demo", ["a.cpp"])
        self.assertEqual(item["chunks_to_remove"], 2)
        self.assertEqual(item["chunks_to_preserve"], 1)
        self.assertEqual(item["documents_to_preserve"], 1)

    def test_invalid_paths_refused(self):
        for selection in ([], ["../a.cpp"], ["/absolute"], ["a.cpp","a.cpp"],
                          ["notfound.cpp"], ["a.cpp\\\\evil"], ["./a.cpp"], [""]):
            with self.subTest(selection=selection):
                with self.assertRaises(KnowledgeDeletionPreviewError):
                    preview_knowledge_removal("demo", selection)

    def test_public_project_denied(self):
        with self.assertRaises(KnowledgeDeletionPreviewError):
            preview_knowledge_removal("codebridge", ["a.cpp"])

    def test_no_enabled_private_index_denied(self):
        with patch(MODULE, return_value=None):
            with self.assertRaises(KnowledgeDeletionPreviewError):
                preview_knowledge_removal("demo", ["a.cpp"])

    def test_database_integrity_required(self):
        self.db.write_bytes(b"NOT_SQLITE")
        with self.assertRaises(sqlite3.DatabaseError):
            preview_knowledge_removal("demo", ["a.cpp"])

    def test_mismatched_document_chunk_inventory_denied(self):
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("DELETE FROM rag_chunks WHERE path='b.md'")
            cn.commit()
        with self.assertRaises(KnowledgeDeletionPreviewError):
            preview_knowledge_removal("demo", ["a.cpp"])

    def test_manifest_chunk_mismatch_refused(self):
        self.entries[0] = SimpleNamespace(
            project_id="demo", path="a.cpp", chunk_ids=("missing",)
        )
        with self.assertRaises(KnowledgeDeletionPreviewError):
            preview_knowledge_removal("demo", ["a.cpp"])

    def test_manifest_path_mismatch_refused(self):
        self.entries[1] = SimpleNamespace(
            project_id="demo", path="unexpected.md", chunk_ids=("b1",)
        )
        with self.assertRaises(KnowledgeDeletionPreviewError):
            preview_knowledge_removal("demo", ["a.cpp"])

    def test_generation_revision_pinned(self):
        first = preview_knowledge_removal("demo", ["a.cpp"])
        with patch(MODULE, return_value=SimpleNamespace(
            sqlite=self.db, manifest=self.root / "manifest.json", generation="auto_next", source_revision="f"*64
        )):
            second = preview_knowledge_removal("demo", ["a.cpp"])
        self.assertNotEqual(first["review_sha256"], second["review_sha256"])
