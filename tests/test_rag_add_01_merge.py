"""RAG-ADD-01: juntar arquivos indexados a um projeto existente (Qdrant e SQLite reais)."""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from unittest.mock import patch

from qdrant_client import models
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest
from rag.index.qdrant_local import close_qdrant_local, ensure_vector_collections, open_qdrant_local
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.isolated_project_index import resolve_isolated_project
from rag.runtime.knowledge_deletion_operational import (
    execute_knowledge_removal, pending_removal, rollback_knowledge_removal,
)
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
import rag.runtime.knowledge_merge_operational as merge
from test_rag_del_close_04_operational import Close04OperationalRemovalTests, PROJECT

JOB2 = "2" * 32
JOB_FILES = (("jb", "bravo.py", "BRAVO_NOVO"), ("jd", "delta.py", "DELTA_NOVO"))


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_generation(folder: Path, snapshot: Path, files, *, project=PROJECT,
                     model="synthetic-test", axis=1) -> dict:
    folder.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    for _, path, body in files:
        (snapshot / path).write_text(body, encoding="utf-8")
    db = folder / "rag_index.sqlite3"
    with closing(connect_rag_index(db)) as con:
        for doc, path, body in files:
            con.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) "
                        "VALUES(?,?,?,?,?,?)", (doc, project, "CODE", body, path, "b" * 64))
            con.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,"
                        "path,sha256) VALUES(?,?,?,?,?,?,?,?)",
                        ("c" + doc, doc, project, 0, body, "CODE", path, "b" * 64))
        con.commit()
        initialize_fts5(con, rebuild=True)
        con.commit()
    manifest = folder / "rag-index-manifest.json"
    save_index_manifest(manifest, IndexManifest(tuple(
        ManifestEntry(project_id=project, index_kind=ManifestIndexKind.CODE, path=path, size=len(body),
                      mtime_ns=2, sha256="b" * 64, chunk_ids=("c" + doc,), model_version=model)
        for doc, path, body in files)))
    client = open_qdrant_local(folder / "qdrant")
    try:
        ensure_vector_collections(client)
        vector = [0.0] * CODE_EMBEDDING_DIMENSION
        vector[axis] = 1.0
        for doc, path, body in files:
            client.upsert("code", points=[models.PointStruct(
                id=deterministic_vector_point_id(project, "code", "c" + doc), vector=vector,
                payload={"chunk_id": "c" + doc, "document_id": doc, "project_namespace": project,
                         "path": path, "sha256": "b" * 64, "source_type": "CODE", "content": body})],
                wait=True)
    finally:
        close_qdrant_local(client)
    return {"project_id": project, "job_id": JOB2, "generation": str(folder),
            "source_snapshot": str(snapshot), "source_revision": "f" * 64,
            "sqlite_sha256": _sha(db), "manifest_sha256": _sha(manifest), "verified": True}


class MergeIntoExistingProjectTests(Close04OperationalRemovalTests):
    def setUp(self):
        super().setUp()
        auto = self.rag.parent / "auto" / "projects" / PROJECT
        self.job = build_generation(auto / "generations" / ("auto_" + JOB2),
                                    auto / "snapshots" / ("source_" + JOB2), JOB_FILES)
        hook = patch.object(merge, "_verified_job_generation", side_effect=lambda job_id: dict(self.job))
        hook.start()
        self.addCleanup(hook.stop)

    def _review(self):
        return merge.preview_knowledge_merge(PROJECT, JOB2)

    def _contents(self, index):
        with closing(sqlite3.connect(Path(index.sqlite).as_uri() + "?mode=ro", uri=True)) as con:
            return {r[0]: r[1] for r in con.execute("SELECT path, content FROM rag_chunks")}

    def _fts(self, index, word):
        with closing(sqlite3.connect(Path(index.sqlite).as_uri() + "?mode=ro", uri=True)) as con:
            return sorted(r[0] for r in con.execute(
                "SELECT path FROM rag_chunks_fts WHERE rag_chunks_fts MATCH ?", (word,)))

    def test_preview_reports_added_and_replaced(self):
        review = self._review()
        self.assertEqual(review["added_paths"], ["delta.py"])
        self.assertEqual(review["replaced_paths"], ["bravo.py"])
        self.assertEqual((review["documents_before"], review["documents_after"]), (3, 4))
        self.assertEqual((review["chunks_before"], review["chunks_after"]), (3, 4))
        self.assertFalse(review["execution_enabled"])

    def test_merge_switches_project_and_keeps_everything_consistent(self):
        before = resolve_isolated_project(PROJECT)
        result = merge.execute_knowledge_merge(PROJECT, JOB2, self._review()["review_sha256"], PROJECT)
        self.assertEqual(result["state"], "MERGED")
        index = resolve_isolated_project(PROJECT)
        self.assertEqual(index.generation, result["generation"])
        self.assertTrue(index.generation.startswith("add_"))
        self.assertNotEqual(index.generation, before.generation)
        self.assertEqual(self._contents(index), {
            "alpha.py": "ALPHA_REMOVE", "bravo.py": "BRAVO_NOVO",
            "charlie.py": "CHARLIE_KEEP", "delta.py": "DELTA_NOVO"})
        self.assertEqual(self._fts(index, "DELTA_NOVO"), ["delta.py"])
        self.assertEqual(self._fts(index, "BRAVO_KEEP"), [])
        client = open_qdrant_local(index.qdrant)
        try:
            self.assertEqual(client.count("code", exact=True).count, 4)
            point = client.retrieve("code", ids=[deterministic_vector_point_id(PROJECT, "code", "cjd")],
                                    with_payload=True)
            self.assertEqual(point[0].payload["path"], "delta.py")
        finally:
            close_qdrant_local(client)
        self.assertEqual((index.source_root / "delta.py").read_text(encoding="utf-8"), "DELTA_NOVO")
        self.assertEqual((index.source_root / "bravo.py").read_text(encoding="utf-8"), "BRAVO_NOVO")
        self.assertEqual((index.source_root / "alpha.py").read_text(encoding="utf-8"), "ALPHA_REMOVE")
        self.assertEqual((self.source / "bravo.py").read_text(encoding="utf-8"), "BRAVO_KEEP")
        self.assertEqual(_sha(self.rag / "active-generation.json"), self.pointer_before)
        self.assertEqual(pending_removal(PROJECT)["transaction"], result["transaction"])

    def test_undo_restores_previous_generation(self):
        before = resolve_isolated_project(PROJECT).generation
        result = merge.execute_knowledge_merge(PROJECT, JOB2, self._review()["review_sha256"], PROJECT)
        rollback_knowledge_removal(result["transaction"])
        index = resolve_isolated_project(PROJECT)
        self.assertEqual(index.generation, before)
        self.assertNotIn("delta.py", self._contents(index))
        self.assertIsNone(pending_removal(PROJECT))

    def test_deletion_works_on_merged_project(self):
        merge.execute_knowledge_merge(PROJECT, JOB2, self._review()["review_sha256"], PROJECT)
        sha = preview_knowledge_removal(PROJECT, ["delta.py"])["review_sha256"]
        execute_knowledge_removal(PROJECT, ["delta.py"], sha, PROJECT)
        index = resolve_isolated_project(PROJECT)
        self.assertNotIn("delta.py", self._contents(index))
        self.assertEqual(self._contents(index)["bravo.py"], "BRAVO_NOVO")

    def test_refusals_leave_catalog_untouched(self):
        catalog = self.catalog.read_bytes()
        good = self._review()["review_sha256"]
        with self.assertRaises(merge.KnowledgeMergeError):
            merge.execute_knowledge_merge(PROJECT, JOB2, good, "outro")
        with self.assertRaises(merge.KnowledgeMergeError):
            merge.execute_knowledge_merge(PROJECT, JOB2, "0" * 64, PROJECT)
        with self.assertRaises(merge.KnowledgeMergeError):
            merge.preview_knowledge_merge("codebridge", JOB2)
        self.job["project_id"] = "outro-projeto"
        with self.assertRaises(merge.KnowledgeMergeError):
            merge.preview_knowledge_merge(PROJECT, JOB2)
        self.assertEqual(self.catalog.read_bytes(), catalog)
        generations = [p.name for p in (self.generation.parent).iterdir()]
        self.assertFalse([n for n in generations if n.startswith("add_")])

    def test_different_embedding_model_refused(self):
        auto = self.rag.parent / "auto2"
        self.job = build_generation(auto / "g", auto / "s", JOB_FILES, model="outro-modelo")
        with self.assertRaises(merge.KnowledgeMergeError):
            self._review()

    def test_tampered_receipt_makes_project_unavailable(self):
        result = merge.execute_knowledge_merge(PROJECT, JOB2, self._review()["review_sha256"], PROJECT)
        receipt = Path(resolve_isolated_project(PROJECT).sqlite).parent / merge.RECEIPT_NAME
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["published_publicly"] = True
        receipt.write_text(json.dumps(data), encoding="utf-8")
        from rag.runtime.isolated_project_index import IsolatedProjectUnavailable
        with self.assertRaises(IsolatedProjectUnavailable):
            resolve_isolated_project(PROJECT)
        self.assertTrue(result["transaction"])


del Close04OperationalRemovalTests