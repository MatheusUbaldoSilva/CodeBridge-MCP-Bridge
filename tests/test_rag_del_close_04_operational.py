"""CLOSE-04: operational removal through the REAL catalog/workspace code path.

LOCALAPPDATA and USERPROFILE are redirected to a temporary directory, so
catalog_path(), _workspace_root() and resolve_isolated_project() run
unpatched against a complete synthetic RAG_AUTO_03 private project.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from qdrant_client import models
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest,
)
from rag.index.qdrant_local import (
    close_qdrant_local, ensure_vector_collections, open_qdrant_local,
)
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.isolated_project_index import resolve_isolated_project
from rag.runtime.knowledge_deletion_operational import (
    KnowledgeRemovalError, execute_knowledge_removal, pending_removal,
    rollback_knowledge_removal,
)
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal

PROJECT = "demo"
JOB = "1" * 32
REVISION = "e" * 64
FILES = (("a", "alpha.py", "ALPHA_REMOVE"),
         ("b", "bravo.py", "BRAVO_KEEP"),
         ("c", "charlie.py", "CHARLIE_KEEP"))


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class Close04OperationalRemovalTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="rag_del_close4_")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        local, home = root / "local", root / "home"
        env = patch.dict(os.environ, {"LOCALAPPDATA": str(local), "USERPROFILE": str(home)})
        env.start()
        self.addCleanup(env.stop)
        self.rag = local / "CodeBridge" / "rag"
        self.rag.mkdir(parents=True)
        project = home / "CodeBridge-RAG-Workspace" / PROJECT
        self.generation = project / "generations" / ("auto_" + JOB)
        self.source = project / "snapshots" / ("source_" + JOB)
        self.generation.mkdir(parents=True)
        self.source.mkdir(parents=True)
        for _, path, body in FILES:
            (self.source / path).write_text(body, encoding="utf-8")
        db = self.generation / "rag_index.sqlite3"
        with closing(connect_rag_index(db)) as con:
            for doc, path, body in FILES:
                con.execute(
                    "INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) "
                    "VALUES(?,?,?,?,?,?)", (doc, PROJECT, "CODE", body, path, "a" * 64))
                con.execute(
                    "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path,sha256) "
                    "VALUES(?,?,?,?,?,?,?,?)", ("c" + doc, doc, PROJECT, 0, body, "CODE", path, "a" * 64))
            con.commit()
            initialize_fts5(con, rebuild=True)
            con.commit()
        manifest = self.generation / "rag-index-manifest.json"
        save_index_manifest(manifest, IndexManifest(tuple(
            ManifestEntry(project_id=PROJECT, index_kind=ManifestIndexKind.CODE, path=path,
                          size=len(body), mtime_ns=1, sha256="a" * 64,
                          chunk_ids=("c" + doc,), model_version="synthetic-test")
            for doc, path, body in FILES)))
        client = open_qdrant_local(self.generation / "qdrant")
        try:
            ensure_vector_collections(client)
            for doc, path, body in FILES:
                client.upsert("code", points=[models.PointStruct(
                    id=deterministic_vector_point_id(PROJECT, "code", "c" + doc),
                    vector=[1.0] + [0.0] * (CODE_EMBEDDING_DIMENSION - 1),
                    payload={"chunk_id": "c" + doc, "document_id": doc,
                             "project_namespace": PROJECT, "path": path,
                             "sha256": "a" * 64, "source_type": "CODE", "content": body},
                )], wait=True)
        finally:
            close_qdrant_local(client)
        (self.generation / "progress.json").write_text(json.dumps({
            "project_id": PROJECT, "source_revision": REVISION, "job_id": JOB,
            "state": "INDEXING_NOT_PUBLISHED", "total_vectors_done": 3,
            "expected_chunks": 3, "last_batch_result": "COMPLETE", "published": False,
        }), encoding="utf-8")
        receipt = self.generation / "auto-generation-receipt.json"
        receipt.write_text(json.dumps({
            "job_id": JOB, "project_id": PROJECT, "source_snapshot": str(self.source.resolve()),
            "source_revision": REVISION, "state": "VERIFIED_NOT_REGISTERED",
            "published_publicly": False,
        }), encoding="utf-8")
        self.catalog = self.rag / "project-indexes.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "projects": {PROJECT: {
            "project_id": PROJECT, "enabled": True, "index_family": "RAG_AUTO_03",
            "job_id": JOB, "source_revision": REVISION,
            "generation_directory": str(self.generation.resolve()),
            "source_directory": str(self.source.resolve()),
            "generation_receipt_sha256": _sha(receipt),
            "sqlite_sha256": _sha(db), "manifest_sha256": _sha(manifest),
            "python_executable": sys.executable,
        }}}, indent=2) + "\n", encoding="utf-8")
        (self.rag / "active-generation.json").write_text(
            json.dumps({"schema_version": 1, "generation": "public-untouched"}), encoding="utf-8")
        self.original_db = _sha(db)
        self.pointer_before = _sha(self.rag / "active-generation.json")

    def _sha_for(self, selection):
        return preview_knowledge_removal(PROJECT, selection)["review_sha256"]

    def _paths(self, index):
        with closing(sqlite3.connect(Path(index.sqlite).as_uri() + "?mode=ro", uri=True)) as con:
            return sorted(r[0] for r in con.execute("SELECT path FROM rag_documents"))

    def test_removes_selected_knowledge_and_switches_project(self):
        self.assertEqual(resolve_isolated_project(PROJECT).generation, "auto_" + JOB)
        result = execute_knowledge_removal(PROJECT, ["alpha.py"], self._sha_for(["alpha.py"]), PROJECT)
        self.assertEqual(result["state"], "REMOVED")
        current = resolve_isolated_project(PROJECT)
        self.assertEqual(current.generation, result["generation"])
        self.assertTrue(current.generation.startswith("del_"))
        self.assertEqual(self._paths(current), ["bravo.py", "charlie.py"])
        self.assertEqual(_sha(self.generation / "rag_index.sqlite3"), self.original_db)
        self.assertTrue((self.source / "alpha.py").is_file())
        self.assertEqual(_sha(self.rag / "active-generation.json"), self.pointer_before)
        self.assertEqual(pending_removal(PROJECT)["transaction"], result["transaction"])

    def test_rollback_restores_previous_generation(self):
        result = execute_knowledge_removal(PROJECT, ["alpha.py"], self._sha_for(["alpha.py"]), PROJECT)
        undo = rollback_knowledge_removal(result["transaction"])
        self.assertEqual(undo["state"], "LAB_ROLLBACK_COMPLETE")
        current = resolve_isolated_project(PROJECT)
        self.assertEqual(current.generation, "auto_" + JOB)
        self.assertEqual(self._paths(current), ["alpha.py", "bravo.py", "charlie.py"])
        self.assertIsNone(pending_removal(PROJECT))

    def test_second_removal_commits_the_first(self):
        first = execute_knowledge_removal(PROJECT, ["alpha.py"], self._sha_for(["alpha.py"]), PROJECT)
        second = execute_knowledge_removal(PROJECT, ["bravo.py"], self._sha_for(["bravo.py"]), PROJECT)
        self.assertEqual(second["committed_previous"], [first["transaction"]])
        self.assertEqual(self._paths(resolve_isolated_project(PROJECT)), ["charlie.py"])
        with self.assertRaises(Exception):
            rollback_knowledge_removal(first["transaction"])
        rollback_knowledge_removal(second["transaction"])
        self.assertEqual(self._paths(resolve_isolated_project(PROJECT)), ["bravo.py", "charlie.py"])

    def _assert_nothing_changed(self, catalog_before):
        self.assertEqual(self.catalog.read_bytes(), catalog_before)
        leftovers = [p.name for p in self.generation.parent.iterdir() if p.name.startswith("del_")]
        self.assertEqual(leftovers, [])

    def test_wrong_confirmation_is_refused(self):
        before = self.catalog.read_bytes()
        with self.assertRaises(KnowledgeRemovalError):
            execute_knowledge_removal(PROJECT, ["alpha.py"], self._sha_for(["alpha.py"]), "outro")
        self._assert_nothing_changed(before)

    def test_stale_preview_is_refused(self):
        before = self.catalog.read_bytes()
        with self.assertRaises(KnowledgeRemovalError):
            execute_knowledge_removal(PROJECT, ["alpha.py"], "0" * 64, PROJECT)
        self._assert_nothing_changed(before)

    def test_public_project_and_total_removal_are_refused(self):
        with self.assertRaises(KnowledgeRemovalError):
            execute_knowledge_removal("codebridge", ["alpha.py"], "0" * 64, "codebridge")
        everything = ["alpha.py", "bravo.py", "charlie.py"]
        with self.assertRaises(KnowledgeRemovalError):
            execute_knowledge_removal(PROJECT, everything, self._sha_for(everything), PROJECT)

    def test_auto_canary_journal_blocks_and_cleans_up(self):
        before = self.catalog.read_bytes()
        (self.rag / ("auto-canary-" + "2" * 32 + ".journal.json")).write_text("{}", encoding="utf-8")
        with self.assertRaises(Exception):
            execute_knowledge_removal(PROJECT, ["alpha.py"], self._sha_for(["alpha.py"]), PROJECT)
        self._assert_nothing_changed(before)