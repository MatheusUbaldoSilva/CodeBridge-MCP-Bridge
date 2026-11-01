"""RAG-DEL closing milestone 02: real read-only preview -> candidate SQL/manifest.

Only a brand new TemporaryDirectory with synthetic documents is used.
No installed GUI, queue, catalog, public index or live file is modified.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import sqlite3

from rag.index.fts5 import initialize_fts5
from rag.index.sqlite_schema import connect_rag_index
from rag.index.manifest import (
    IndexManifest, ManifestEntry, ManifestIndexKind,
    save_index_manifest, load_index_manifest,
)
from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
from rag.runtime.knowledge_deletion_preview_binding_dev import (
    review_deletion_preview_binding_dev,
)
from rag.runtime.knowledge_deletion_stage import (
    stage_removal_sqlite_manifest, DeletionStageError,
)
from qdrant_client import models
from rag.index.qdrant_local import (
    open_qdrant_local, close_qdrant_local, ensure_vector_collections,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.knowledge_deletion_vectors import plan_surviving_vector_batches
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch
from rag.runtime.knowledge_deletion_checkpoint import checkpoint_survivor_batch
from rag.runtime.knowledge_deletion_verify import validate_deletion_candidate

PROJECT="demo"
REVISION="f"*64
GENERATION="lab-unchanged"
RESOLVERS=(
    "rag.runtime.knowledge_deletion_preview.resolve_isolated_project",
    "rag.runtime.knowledge_deletion_stage.resolve_isolated_project",
)


class Close02SyntheticPreviewStagingTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory(prefix="rag_del_close2_")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.source=self.root/"original"
        self.source.mkdir()
        self.db=self.source/"rag_index.sqlite3"
        self.manifest=self.source/"rag-index-manifest.json"
        self.content=(("a","alpha.py","ALPHA_PLACEHOLDER"),
                      ("b","bravo.py","BRAVO_PRESERVED"),
                      ("c","charlie.py","CHARLIE_PRESERVED"))
        with closing(connect_rag_index(self.db)) as con:
            for doc_id,path,body in self.content:
                con.execute(
                    "INSERT INTO rag_documents("
                    "document_id,project_id,source_type,content,path,sha256) "
                    "VALUES(?,?,?,?,?,?)",
                    (doc_id,PROJECT,"CODE",body,path,"a"*64),
                )
                con.execute(
                    "INSERT INTO rag_chunks("
                    "chunk_id,document_id,project_id,ordinal,content,source_type,path,sha256) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    ("c"+doc_id,doc_id,PROJECT,0,body,"CODE",path,"a"*64),
                )
            con.commit()
            initialize_fts5(con,rebuild=True)
            con.commit()
        save_index_manifest(self.manifest,IndexManifest(tuple(
            ManifestEntry(
                project_id=PROJECT,index_kind=ManifestIndexKind.CODE,
                path=path,size=len(body),mtime_ns=1,
                sha256="a"*64,chunk_ids=("c"+doc_id,),
                model_version="synthetic-test",
            )
            for doc_id,path,body in self.content
        )))
        self.original_db=sha256(self.db.read_bytes()).hexdigest()
        self.original_manifest=sha256(self.manifest.read_bytes()).hexdigest()
        self.identity=SimpleNamespace(
            sqlite=self.db,manifest=self.manifest,
            generation=GENERATION,source_revision=REVISION,
        )
        for target in RESOLVERS:
            replacement=patch(target,return_value=self.identity)
            replacement.start()
            self.addCleanup(replacement.stop)

    def _preview(self,selection):
        result=preview_knowledge_removal(PROJECT,selection)
        check=review_deletion_preview_binding_dev(
            PROJECT,selection,result,expected_generation=GENERATION,
            expected_source_revision=REVISION,
        )
        self.assertEqual(check["state"],"F16_DEV_PREVIEW_FIELDS_COHERENT_NO_AUTHORITY")
        self.assertFalse(check["activation_authorized"])
        return result

    def _original_unchanged(self):
        self.assertEqual(sha256(self.db.read_bytes()).hexdigest(),self.original_db)
        self.assertEqual(sha256(self.manifest.read_bytes()).hexdigest(),self.original_manifest)

    def test_selected_doc_removed_only_in_candidate(self):
        preview=self._preview(["alpha.py"])
        self.assertEqual(preview["documents_to_remove"],1)
        self.assertEqual(preview["documents_to_preserve"],2)
        destination=self.root/"candidate"
        result=stage_removal_sqlite_manifest(PROJECT,["alpha.py"],
                                             preview["review_sha256"],destination)
        self.assertEqual(result["documents"],2)
        self.assertEqual(result["chunks"],2)
        self.assertEqual(result["fts_chunks"],2)
        self.assertFalse(result["activated"])
        self.assertFalse(result["public_pointer_updated"])
        with closing(sqlite3.connect(destination/"rag_index.sqlite3")) as con:
            for table in ("rag_documents","rag_chunks","rag_chunks_fts"):
                paths=[x[0] for x in con.execute(
                    f"SELECT path FROM {table} ORDER BY path").fetchall()]
                self.assertEqual(paths,["bravo.py","charlie.py"],table)
            remaining=[row[0] for row in con.execute(
                "SELECT content FROM rag_documents ORDER BY path")]
            self.assertEqual(remaining,["BRAVO_PRESERVED","CHARLIE_PRESERVED"])
        self.assertEqual(
            [e.path for e in load_index_manifest(destination/"rag-index-manifest.json").entries],
            ["bravo.py","charlie.py"],
        )
        self._original_unchanged()
        source=self._preview(["alpha.py"])
        self.assertEqual(source["documents_to_preserve"],2)

    def test_multiple_selected_files_remove_only_from_candidate(self):
        requested=["charlie.py","alpha.py"]
        preview=self._preview(requested)
        result=stage_removal_sqlite_manifest(
            PROJECT,requested,preview["review_sha256"],self.root/"candidate")
        self.assertEqual((result["documents"],result["chunks"],result["fts_chunks"]),(1,1,1))
        self.assertEqual(
            [e.path for e in load_index_manifest(self.root/"candidate"/"rag-index-manifest.json").entries],
            ["bravo.py"],
        )
        self._original_unchanged()

    def test_actual_preview_stages_and_verifies_surviving_qdrant_vectors(self):
        """Real preview -> staged SQLite/manifest -> surviving vectors -> verify."""
        selected=["alpha.py"]
        preview=self._preview(selected)
        stage=self.root/"candidate"
        stage_receipt=stage_removal_sqlite_manifest(
            PROJECT,selected,preview["review_sha256"],stage)
        self.assertFalse(stage_receipt["activated"])
        with patch(
            "rag.runtime.knowledge_deletion_vectors.resolve_isolated_project",
            return_value=self.identity,
        ):
            plan=plan_surviving_vector_batches(self.manifest,preview)
        self.assertEqual(plan["vectors_to_preserve"],2)
        source=open_qdrant_local(self.root/"source_qdrant")
        destination=open_qdrant_local(stage/"qdrant")
        try:
            ensure_vector_collections(source)
            ensure_vector_collections(destination)
            for doc_id,path,body in self.content:
                if doc_id=="a":
                    continue
                point_id=deterministic_vector_point_id(PROJECT,"code","c"+doc_id)
                payload={
                    "chunk_id":"c"+doc_id,"document_id":doc_id,
                    "project_namespace":PROJECT,"path":path,
                    "sha256":"a"*64,"source_type":"CODE","content":body,
                }
                source.upsert("code",points=[models.PointStruct(
                    id=point_id,
                    vector=[1.0]+[0.0]*(CODE_EMBEDDING_DIMENSION-1),
                    payload=payload,
                )],wait=True)
            copy=copy_survivor_batch(
                source,destination,plan,0,
                verified_source=True,isolated_staging=True,
                operator_approved=True,
            )
            receipt=checkpoint_survivor_batch(
                destination,stage,"c"*32,copy,plan["batches"][0],
                plan["sources"],operator_approved=True,
            )
            self.assertEqual(receipt["vectors_verified"],2)
            result=validate_deletion_candidate(
                stage,plan,destination,["c"*32],
            )
            self.assertEqual(result["documents"],2)
            self.assertEqual(result["chunks"],2)
            self.assertEqual(result["vectors_verified"],2)
            self.assertFalse(result["activation_authorized"])
        finally:
            close_qdrant_local(destination)
            close_qdrant_local(source)
        self._original_unchanged()

    def test_stale_preview_digest_rejected_before_creating_stage(self):
        self._preview(["alpha.py"])
        destination=self.root/"candidate"
        with self.assertRaises(DeletionStageError):
            stage_removal_sqlite_manifest(PROJECT,["alpha.py"],"0"*64,destination)
        self.assertFalse(destination.exists())
        self._original_unchanged()

    def test_changed_generation_rejected_before_candidate(self):
        preview=self._preview(["alpha.py"])
        destination=self.root/"candidate"
        different=SimpleNamespace(
            sqlite=self.db,manifest=self.manifest,
            generation="other-generation",source_revision=REVISION,
        )
        with patch(RESOLVERS[1],return_value=different):
            with self.assertRaises(DeletionStageError):
                stage_removal_sqlite_manifest(
                    PROJECT,["alpha.py"],preview["review_sha256"],destination)
        self.assertFalse(destination.exists())
        self._original_unchanged()

    def test_destination_never_overwrites_existing_path(self):
        preview=self._preview(["alpha.py"])
        destination=self.root/"candidate"
        destination.mkdir()
        sentinel=destination/"keep-me.txt"
        sentinel.write_text("PRESERVE",encoding="utf-8")
        with self.assertRaises(DeletionStageError):
            stage_removal_sqlite_manifest(
                PROJECT,["alpha.py"],preview["review_sha256"],destination)
        self.assertEqual(sentinel.read_text(encoding="utf-8"),"PRESERVE")
        self._original_unchanged()

    def test_public_project_rejected(self):
        with self.assertRaises(ValueError):
            preview_knowledge_removal("codebridge",["alpha.py"])
        self._original_unchanged()

    def test_original_still_has_all_three_documents(self):
        self._preview(["alpha.py"])
        with closing(sqlite3.connect(self.db)) as con:
            original=[r[0] for r in con.execute(
                "SELECT path FROM rag_documents ORDER BY path").fetchall()]
            self.assertEqual(original,["alpha.py","bravo.py","charlie.py"])
        self._original_unchanged()
