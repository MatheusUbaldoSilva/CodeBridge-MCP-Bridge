import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import upsert_vector_chunk
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.ranking.dedup import deduplicate_ranked_results
from rag.ranking.rrf import reciprocal_rank_fusion
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.runtime.query_classifier import QueryRoute


CASES = (
    ("cancelamento", "chunk-cancel", 0),
    ("handoff memoria", "chunk-memory", 1),
    ("runtime wait", "chunk-wait", 2),
)


def basis(dimension, index):
    values = [0.0] * dimension
    values[index] = 1.0
    return values


class Rag010RetrievalBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_rag_index(":memory:")
        self.addCleanup(self.connection.close)

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vector_client = open_qdrant_local(
            Path(self.temp.name) / "qdrant"
        )
        self.addCleanup(
            lambda: close_qdrant_local(self.vector_client)
        )
        ensure_vector_collections(self.vector_client)

        for query_text, chunk_id, index in CASES:
            document_id = f"doc-{index}"
            source_type = (
                SourceType.CODE
                if index == 2
                else SourceType.DOCUMENTATION
            )
            content = (
                f"{query_text} referência técnica estável para benchmark"
            )

            self.connection.execute(
                """
                INSERT INTO rag_documents (
                    document_id,
                    project_id,
                    source_type,
                    content
                ) VALUES (?, 'codebridge', ?, ?)
                """,
                (
                    document_id,
                    source_type.value,
                    content,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO rag_chunks (
                    chunk_id,
                    document_id,
                    project_id,
                    ordinal,
                    content,
                    source_type
                ) VALUES (?, ?, 'codebridge', 0, ?, ?)
                """,
                (
                    chunk_id,
                    document_id,
                    content,
                    source_type.value,
                ),
            )

            payload = {
                "document_id": document_id,
                "content": content,
                "source_type": source_type.value,
            }

            upsert_vector_chunk(
                self.vector_client,
                collection_name=TEXT_VECTOR_COLLECTION,
                project_id="codebridge",
                chunk_id=chunk_id,
                vector=basis(TEXT_EMBEDDING_DIMENSION, index),
                payload=payload,
            )
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id="codebridge",
                chunk_id=chunk_id,
                vector=basis(CODE_EMBEDDING_DIMENSION, index),
                payload=payload,
            )

        self.connection.commit()
        initialize_fts5(self.connection)

    def test_three_case_hybrid_retrieval_benchmark(self):
        reciprocal_ranks = []
        hits_at_1 = 0
        hits_at_3 = 0

        for query_text, expected_chunk, index in CASES:
            candidates = collect_hybrid_query_candidates(
                self.connection,
                self.vector_client,
                SearchQuery(
                    query=query_text,
                    project_id="codebridge",
                    top_k=3,
                ),
                route=QueryRoute.HYBRID,
                text_query_vector=basis(
                    TEXT_EMBEDDING_DIMENSION,
                    index,
                ),
                code_query_vector=basis(
                    CODE_EMBEDDING_DIMENSION,
                    index,
                ),
            )

            fused = reciprocal_rank_fusion(
                (
                    candidates.lexical,
                    candidates.text_vector,
                    candidates.code_vector,
                ),
                top_k=3,
            )
            final = deduplicate_ranked_results(
                fused,
                top_k=3,
            ).results

            ranked_ids = [item.chunk_id for item in final]
            position = ranked_ids.index(expected_chunk) + 1

            reciprocal_ranks.append(1.0 / position)
            hits_at_1 += int(position <= 1)
            hits_at_3 += int(position <= 3)

        count = len(CASES)
        hit_at_1 = hits_at_1 / count
        recall_at_3 = hits_at_3 / count
        mrr = sum(reciprocal_ranks) / count

        self.assertEqual(hit_at_1, 1.0)
        self.assertEqual(recall_at_3, 1.0)
        self.assertEqual(mrr, 1.0)


if __name__ == "__main__":
    unittest.main()
