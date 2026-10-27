"""RAG-AUTO-05-E verified Qdrant isolated source-to-target smoke."""
from pathlib import Path
import tempfile
import unittest
from qdrant_client import models

from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local,ensure_vector_collections
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.runtime.auto_index_incremental_read import read_reusable_vectors
from rag.runtime.auto_index_incremental_execute import execute_isolated_reuse_batch
from rag.runtime.auto_index_incremental_checkpoint import read_isolated_batch_receipt
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.runtime.auto_index_incremental_verify import verify_isolated_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class QdrantTransferLabTests(unittest.TestCase):
    def test_transfer_between_two_fresh_isolated_qdrant_stores(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-transfer-") as temporary:
            root=Path(temporary)
            source=open_qdrant_local(root/"immutable-baseline")
            target=open_qdrant_local(root/"isolated-candidate")
            try:
                ensure_vector_collections(source)
                ensure_vector_collections(target)
                project="ragauto05-transfer-lab"
                chunk="text-example-chunk"
                point_id=deterministic_vector_point_id(project,"text",chunk)
                payload={
                    "project_namespace":project,"chunk_id":chunk,
                    "path":"readme.md","sha256":"a"*64,"source_type":"DOCUMENTATION",
                }
                source.upsert(
                    collection_name="text",
                    points=[models.PointStruct(
                        id=point_id,vector=[0.01]*TEXT_EMBEDDING_DIMENSION,
                        payload=payload,
                    )],
                    wait=True,
                )
                receipt={
                    "mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                    "candidate_chunk_ids":{"readme.md":[chunk]},
                    "vector_copy_authorized":False,
                }
                reviewed={"sources":[{"path":"readme.md",
                     "sha256":"a"*64,"index_kind":"TEXT"}]}
                records=read_reusable_vectors(source,receipt,reviewed)
                self.assertEqual(len(records["TEXT"]),1)
                stage=root/"checkpoint"
                stage.mkdir()
                written=execute_isolated_reuse_batch(
                    target,stage,receipt,reviewed,records,
                    approve_isolated_stage=True,batch_id="f"*32,
                )
                self.assertEqual(written["vectors_written"],1)
                self.assertEqual(read_isolated_batch_receipt(stage,"f"*32)["vectors_written"],1)
                verification=verify_isolated_reuse_batch(target,stage,"f"*32,receipt,reviewed)
                self.assertTrue(verification["revalidation_passed"])
                self.assertEqual(verification["checked_vectors"],1)
                verification=verify_isolated_reuse_batch(target,stage,"f"*32,receipt,reviewed)
                self.assertTrue(verification["revalidation_passed"])
                self.assertEqual(verification["checked_vectors"],1)
                actual=target.retrieve(
                    collection_name="text",ids=[point_id],
                    with_payload=True,with_vectors=True)
                self.assertEqual(len(actual),1)
                self.assertEqual(actual[0].payload["sha256"],"a"*64)
                target.delete(collection_name="text",points_selector=[point_id],wait=True)
                with self.assertRaises(IncrementalPlanError):
                    verify_isolated_reuse_batch(target,stage,"f"*32,receipt,reviewed)
                self.assertEqual(len(actual[0].vector),TEXT_EMBEDDING_DIMENSION)
                self.assertFalse(written["public_pointer_updated"])
            finally:
                close_qdrant_local(source)
                close_qdrant_local(target)

    def test_source_read_refuses_previously_authorized_copy_receipt(self):
        from unittest.mock import Mock
        sample={"mode":"CHUNK_RECEIPT_ONLY","project_id":"test",
                "candidate_chunk_ids":{},"vector_copy_authorized":True}
        with self.assertRaises(IncrementalPlanError):
            read_reusable_vectors(Mock(),sample,{"sources":[]})
        with self.assertRaises(IncrementalPlanError):
            read_reusable_vectors(Mock(),None,{"sources":[]})

    def test_missing_source_point_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-empty-") as temporary:
            source=open_qdrant_local(Path(temporary)/"empty")
            try:
                ensure_vector_collections(source)
                receipt={
                    "mode":"CHUNK_RECEIPT_ONLY","project_id":"ragauto05-lab",
                    "candidate_chunk_ids":{"readme.md":["missing"]},
                    "vector_copy_authorized":False}
                reviewed={"sources":[{"path":"readme.md",
                    "sha256":"a"*64,"index_kind":"TEXT"}]}
                with self.assertRaises(IncrementalPlanError):
                    read_reusable_vectors(source,receipt,reviewed)
            finally:
                close_qdrant_local(source)
