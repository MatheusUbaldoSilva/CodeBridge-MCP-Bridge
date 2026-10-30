"""Temporary Qdrant local canary: surviving vector copied without model inference."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from qdrant_client import models

from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local,ensure_vector_collections
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch


class SurvivorQdrantCanary(TestCase):
    def test_copy_valid_source_to_independent_stage(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            source=open_qdrant_local(root/"source"/"qdrant")
            stage=open_qdrant_local(root/"stage"/"qdrant")
            try:
                ensure_vector_collections(source)
                ensure_vector_collections(stage)
                point_id=deterministic_vector_point_id("demo","code","chunk123")
                source.upsert("code",points=[models.PointStruct(
                    id=point_id,
                    vector=[1.0]+[0.0]*(CODE_EMBEDDING_DIMENSION-1),
                    payload={"chunk_id":"chunk123","path":"keep.cpp",
                             "sha256":"a"*64,"project_namespace":"demo",
                             "source_type":"CODE","content":"abc"},
                )],wait=True)
                receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":"demo",
                         "candidate_chunk_ids":{"keep.cpp":["chunk123"]},
                         "candidate_vector_count":1,"vector_copy_authorized":False}
                plan={"state":"SURVIVOR_RECEIPTS_ONLY","project_id":"demo",
                      "activation_authorized":False,"batches":[receipt],
                      "sources":{"sources":[{"path":"keep.cpp","sha256":"a"*64,
                                             "index_kind":"CODE"}]}}
                result=copy_survivor_batch(source,stage,plan,0,
                    verified_source=True,isolated_staging=True,operator_approved=True)
                self.assertEqual(result["vectors_verified"],1)
                self.assertFalse(result["generation_activated"])
                self.assertEqual(len(stage.retrieve("code",[point_id],with_vectors=True)),1)
                self.assertEqual(len(source.retrieve("code",[point_id],with_vectors=True)),1)
            finally:
                close_qdrant_local(stage)
                close_qdrant_local(source)
