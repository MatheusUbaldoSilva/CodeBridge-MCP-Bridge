"""RAG-DEL multi-batch candidate validation with real temporary Qdrant."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import uuid

from qdrant_client import models
from rag.index.sqlite_schema import connect_rag_index
from rag.index.fts5 import initialize_fts5
from rag.index.manifest import IndexManifest,ManifestEntry,ManifestIndexKind,save_index_manifest
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local,ensure_vector_collections
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch
from rag.runtime.knowledge_deletion_checkpoint import checkpoint_survivor_batch
from rag.runtime.knowledge_deletion_verify import validate_deletion_candidate
from rag.runtime.auto_index_incremental_batches import partition_reuse_receipt
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class MultiBatchCandidateTests(TestCase):
    def test_batched_candidate_and_missing_batch_detection(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            stage=root/"stage"
            stage.mkdir()
            db=stage/"rag_index.sqlite3"
            sources=[]
            entries=[]
            chunks={}
            with closing(connect_rag_index(db)) as cn:
                for i in range(5):
                    path="keep%d.cpp"%i
                    ident="chunk%d"%i
                    cn.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) VALUES(?,?,?,?,?,?)",
                        ("doc%d"%i,"demo","CODE",ident,path,"a"*64))
                    cn.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path,sha256) VALUES(?,?,?,?,?,?,?,?)",
                        (ident,"doc%d"%i,"demo",0,ident,"CODE",path,"a"*64))
                    entries.append(ManifestEntry(project_id="demo",index_kind=ManifestIndexKind.CODE,
                         path=path,size=1,mtime_ns=1,sha256="a"*64,
                         chunk_ids=(ident,),model_version="test"))
                    sources.append({"path":path,"sha256":"a"*64,"index_kind":"CODE"})
                    chunks[path]=[ident]
                cn.commit()
                initialize_fts5(cn,rebuild=True)
                cn.commit()
            save_index_manifest(stage/"rag-index-manifest.json",IndexManifest(tuple(entries)))
            receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":"demo","candidate_chunk_ids":chunks,
                     "candidate_vector_count":5,"vector_copy_authorized":False}
            reviewed={"sources":sources}
            batches=partition_reuse_receipt(receipt,reviewed,max_vectors=2)
            self.assertEqual([b["candidate_vector_count"] for b in batches],[2,2,1])
            plan={"state":"SURVIVOR_RECEIPTS_ONLY","project_id":"demo","sources":reviewed,
                  "batches":batches,"vectors_to_preserve":5,"activation_authorized":False}
            source=open_qdrant_local(root/"source")
            dest=open_qdrant_local(stage/"qdrant")
            try:
                ensure_vector_collections(source)
                ensure_vector_collections(dest)
                for i in range(5):
                    source.upsert("code",points=[models.PointStruct(
                        id=deterministic_vector_point_id("demo","code","chunk%d"%i),
                        vector=[1.0]+[0.0]*(CODE_EMBEDDING_DIMENSION-1),
                        payload={"chunk_id":"chunk%d"%i,"path":"keep%d.cpp"%i,
                                "sha256":"a"*64,"project_namespace":"demo","source_type":"CODE"}
                    )],wait=True)
                batch_ids=[]
                for index in range(3):
                    result=copy_survivor_batch(source,dest,plan,index,verified_source=True,
                         isolated_staging=True,operator_approved=True,max_vectors=2)
                    batch_id=uuid.uuid4().hex
                    checkpoint_survivor_batch(dest,stage,batch_id,result,batches[index],reviewed,
                         operator_approved=True,max_vectors=2)
                    batch_ids.append(batch_id)
                verified=validate_deletion_candidate(stage,plan,dest,batch_ids)
                self.assertEqual(verified["vectors_verified"],5)
                self.assertEqual(verified["batches_verified"],3)
                with self.assertRaises(IncrementalPlanError):
                    validate_deletion_candidate(stage,plan,dest,batch_ids[:-1])
                # Tampering with the payload after a valid checkpoint must fail.
                victim=deterministic_vector_point_id("demo","code","chunk0")
                dest.set_payload(collection_name="code",
                    payload={"sha256":"b"*64},points=[victim])
                with self.assertRaises(IncrementalPlanError):
                    validate_deletion_candidate(stage,plan,dest,batch_ids)
                (stage/("batch_"+batch_ids[1]+".json")).unlink()
                with self.assertRaises(IncrementalPlanError):
                    validate_deletion_candidate(stage,plan,dest,batch_ids)
            finally:
                close_qdrant_local(dest)
                close_qdrant_local(source)
