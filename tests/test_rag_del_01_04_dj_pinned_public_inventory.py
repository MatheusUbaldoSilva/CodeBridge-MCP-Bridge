"""RAG-DEL-01.04-DJ: pinned read-only public inventory, synthetic versioned RAG."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_public_inventory_read import (
    read_pinned_public_document_inventory,
)
from rag.runtime.production_generation_lock import ProductionGenerationBusy


_CHILD = r"""
from pathlib import Path
import sys
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"rag_index.sqlite3"):
    with production_generation_lock(exclusive=True,channel="generation"):
        print("LOCKED",flush=True)
        sys.stdin.readline()
"""


class PublicInventoryPinnedTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "CodeBridge" / "rag"
        self.version = "v1_delta_abcdef12345678"
        folder = self.root / "generations" / self.version
        folder.mkdir(parents=True)
        self.sqlite = folder / "rag_index.sqlite3"
        with closing(sqlite3.connect(self.sqlite)) as db:
            db.execute(
                "CREATE TABLE rag_documents (project_id TEXT,path TEXT,source_type TEXT)"
            )
            db.executemany("INSERT INTO rag_documents VALUES (?,?,?)", [
                ("codebridge", "src/z.py", "CODE"),
                ("codebridge", "src/z.py", "CODE"),
                ("codebridge", "src/a.md", "TEXT"),
                ("newworldpvp", "secret/file.py", "CODE"),
            ])
            db.commit()
        (folder / "qdrant").mkdir()
        (folder / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
        (self.root / "active-generation.json").write_text(
            json.dumps({"schema_version": 1, "generation": self.version}),
            encoding="utf-8",
        )

    def inventory(self, **kwargs):
        with (
            patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
                  return_value=self.root / "rag_index.sqlite3"),
            patch("rag.runtime.production_generation_read.resolve_rag_sqlite_path",
                  return_value=self.root / "rag_index.sqlite3"),
        ):
            return read_pinned_public_document_inventory(**kwargs)

    def test_pinned_inventory_excludes_foreign_namespace_and_is_read_only(self):
        before = self.sqlite.read_bytes()
        result = self.inventory()
        self.assertEqual(result["generation"], self.version)
        self.assertEqual(result["state"], "PUBLIC_DOCUMENT_INVENTORY_READ_ONLY")
        self.assertEqual(result["documents"], [
            {"path": "src/a.md", "count": 1, "type": "TEXT"},
            {"path": "src/z.py", "count": 2, "type": "CODE"},
        ])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertTrue(result["read_only"])
        self.assertEqual(self.sqlite.read_bytes(), before)

    def test_private_namespace_and_invalid_limit_rejected_before_read(self):
        with self.assertRaises(ValueError):
            self.inventory(project_id="newworldpvp")
        for invalid in (0, 2001, True, "10"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.inventory(limit=invalid)
        self.assertEqual(len(self.inventory(limit=1)["documents"]), 1)

    def test_transition_journal_fails_closed(self):
        (self.root / "production-generation-transition.json").write_text(
            "{}", encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "transition pending"):
            self.inventory()

    def test_sqlite_symlink_predicate_fails_closed(self):
        with patch.object(
            Path, "is_symlink", autospec=True,
            side_effect=lambda p: p == self.sqlite,
        ):
            with self.assertRaisesRegex(RuntimeError, "redirected public SQLite"):
                self.inventory()

    def test_exclusive_generation_cutover_blocks_inventory(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(ProductionGenerationBusy):
                self.inventory()
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n", timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        self.assertEqual(self.inventory()["state"], "PUBLIC_DOCUMENT_INVENTORY_READ_ONLY")