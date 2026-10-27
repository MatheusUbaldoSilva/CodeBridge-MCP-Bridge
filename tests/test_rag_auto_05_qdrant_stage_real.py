"""RAG-AUTO-05-E actual Qdrant Local isolated vector transfer smoke test."""
from pathlib import Path
import tempfile
import unittest

from rag.index.qdrant_local import (
    open_qdrant_local, close_qdrant_local, ensure_vector_collections,
)
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.runtime.auto_index_incremental_stage_write import import_verified_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class RealQdrantLocalStageTests(unittest.TestCase):
    def test_isolated_single_text_vector_import_and_replay_denial(self):
        from qdrant_client import models
        with tempfile.TemporaryDirectory(prefix="ragauto05-qdrant-lab-") as tmp:
            project="ragauto05-canary"
            path=Path(tmp)/"isolated-new-qdrant"
            client=open_qdrant_local(path)
            try:
                ensure_vector_collections(client)
                chunk="lab-text-chunk"
                identity=deterministic_vector_point_id(project,"text",chunk)
                receipt={"mode":"CHUNK_RECEIPT_ONLY","project_id":project,
                         "candidate_chunk_ids":{"src/readme.md":[chunk]},
                         "vector_copy_authorized":False}
                sources={"sources":[{"path":"src/readme.md",
                                     "sha256":"a"*64,"index_kind":"TEXT"}]}
                records={"TEXT":[{"id":identity,
                          "vector":[0.001]*TEXT_EMBEDDING_DIMENSION,
                          "payload":{"project_namespace":project,
                                     "chunk_id":chunk,"path":"src/readme.md",
                                     "sha256":"a"*64,"source_type":"DOCUMENTATION"}}],
                         "CODE":[]}
                result=import_verified_reuse_batch(
                    client,receipt,sources,records,
                    isolated_destination=True,allow_stage_write=True)
                self.assertEqual(result["vectors_written"],1)
                actual=client.retrieve(
                    collection_name="text",ids=[identity],
                    with_vectors=True,with_payload=True,
                )
                self.assertEqual(len(actual),1)
                self.assertEqual(actual[0].payload["chunk_id"],chunk)
                self.assertEqual(len(actual[0].vector),TEXT_EMBEDDING_DIMENSION)
                with self.assertRaises(IncrementalPlanError):
                    import_verified_reuse_batch(
                        client,receipt,sources,records,
                        isolated_destination=True,allow_stage_write=True)
            finally:
                close_qdrant_local(client)
