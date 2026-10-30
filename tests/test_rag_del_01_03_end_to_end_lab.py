"""End-to-end deletion candidate laboratory with temporary SQLite and Qdrant."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from qdrant_client import models

from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local,ensure_vector_collections
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.knowledge_deletion_stage import stage_removal_sqlite_manifest
from rag.runtime.knowledge_deletion_vectors import plan_surviving_vector_batches
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch
from rag.runtime.knowledge_deletion_checkpoint import checkpoint_survivor_batch
from rag.runtime.knowledge_deletion_verify import validate_deletion_candidate


class DeletionCandidateE2ETests(TestCase):
    def test_isolated_source_preserved_end_to_end(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            active=root/"active"
            active.mkdir()
            db=active/"rag_index.sqlite3"
            manifest=active/"rag-index-manifest.json"
            with closing(connect_rag_index(db)) as con:
                for key in ("a","b"):
                    con.execute(
                        "INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) "
                        "VALUES(?,?,?,?,?,?)",(key,"demo","CODE","test",key+".cpp","a"*64))
                    con.execute(
                        "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path,sha256) "
                        "VALUES(?,?,?,?,?,?,?,?)",("c"+key,key,"demo",0,"test","CODE",key+".cpp","a"*64))
                con.commit()
                initialize_fts5(con,rebuild=True)
                con.commit()
            save_index_manifest(manifest,IndexManifest(tuple(
                ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                    path=key+".cpp",size=1,mtime_ns=1,sha256="a"*64,
                    chunk_ids=("c"+key,),model_version="test")
                for key in ("a","b")
            )))
            original_db=db.read_bytes()
            original_manifest=manifest.read_bytes()
            identity=SimpleNamespace(sqlite=db,manifest=manifest,generation="auto_fake",
                                     source_revision="f"*64)
            preview={"mode":"READ_ONLY_REMOVAL_PREVIEW","project_id":"demo",
                     "generation":"auto_fake","source_revision":"f"*64,
                     "review_sha256":"b"*64,"selected_paths":["a.cpp"],
                     "documents_to_preserve":1,"chunks_to_preserve":1,
                     "deletion_authorized":False,"candidate_created":False}
            with patch("rag.runtime.knowledge_deletion_stage.preview_knowledge_removal",return_value=preview),\
                 patch("rag.runtime.knowledge_deletion_stage.resolve_isolated_project",return_value=identity),\
                 patch("rag.runtime.knowledge_deletion_vectors.preview_knowledge_removal",return_value=preview),\
                 patch("rag.runtime.knowledge_deletion_vectors.resolve_isolated_project",return_value=identity):
                stage=root/"candidate"
                result=stage_removal_sqlite_manifest("demo",["a.cpp"],"b"*64,stage)
                self.assertFalse(result["activated"])
                plan=plan_surviving_vector_batches(manifest,preview)
            self.assertEqual(plan["vectors_to_preserve"],1)
            source=open_qdrant_local(root/"source_qdrant")
            target=open_qdrant_local(stage/"qdrant")
            try:
                ensure_vector_collections(source)
                ensure_vector_collections(target)
                point_id=deterministic_vector_point_id("demo","code","cb")
                payload={"chunk_id":"cb","document_id":"b","project_namespace":"demo",
                         "path":"b.cpp","sha256":"a"*64,"source_type":"CODE",
                         "content":"test"}
                source.upsert("code",points=[models.PointStruct(
                    id=point_id,vector=[1.0]+[0.0]*(CODE_EMBEDDING_DIMENSION-1),
                    payload=payload,
                )],wait=True)
                copied=copy_survivor_batch(source,target,plan,0,
                    verified_source=True,isolated_staging=True,operator_approved=True)
                checkpoint=checkpoint_survivor_batch(
                    target,stage,"c"*32,copied,plan["batches"][0],plan["sources"],
                    operator_approved=True)
                self.assertEqual(checkpoint["vectors_verified"],1)
                checked=validate_deletion_candidate(stage,plan,target,["c"*32])
                self.assertEqual(checked["documents"],1)
                self.assertEqual(checked["chunks"],1)
                self.assertEqual(checked["vectors_verified"],1)
                self.assertFalse(checked["activation_authorized"])
            finally:
                close_qdrant_local(target)
                close_qdrant_local(source)
            self.assertEqual(db.read_bytes(),original_db)
            self.assertEqual(manifest.read_bytes(),original_manifest)
