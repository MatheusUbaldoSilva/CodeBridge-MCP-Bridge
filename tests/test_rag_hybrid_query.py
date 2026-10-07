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
from rag.retrieval.hybrid_query import (
    HybridQueryCandidates,
    collect_hybrid_query_candidates,
)
from rag.runtime.query_classifier import QueryRoute, classify_query


def insert_document(
    connection,
    document_id,
    *,
    project_id="codebridge",
    source_type="DOCUMENTATION",
):
    connection.execute(
        """
        INSERT INTO rag_documents (
            document_id,
            project_id,
            source_type,
            content
        ) VALUES (?, ?, ?, 'source')
        """,
        (document_id, project_id, source_type),
    )


def insert_chunk(
    connection,
    *,
    chunk_id,
    document_id,
    content,
    source_type,
    project_id="codebridge",
):
    connection.execute(
        """
        INSERT INTO rag_chunks (
            chunk_id,
            document_id,
            project_id,
            ordinal,
            content,
            source_type
        ) VALUES (?, ?, ?, 0, ?, ?)
        """,
        (
            chunk_id,
            document_id,
            project_id,
            content,
            source_type,
        ),
    )


def payload(
    *,
    document_id,
    content,
    source_type,
):
    return {
        "document_id": document_id,
        "content": content,
        "source_type": source_type,
    }


class RagHybridQueryTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_rag_index(":memory:")
        self.addCleanup(self.connection.close)
        initialize_fts5(self.connection)

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.vector_client = open_qdrant_local(
            Path(self.temp.name) / "qdrant"
        )
        self.addCleanup(
            lambda: close_qdrant_local(self.vector_client)
        )
        ensure_vector_collections(self.vector_client)

        self.text_query_vector = [1.0] + [0.0] * (
            TEXT_EMBEDDING_DIMENSION - 1
        )
        self.code_query_vector = [1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 1
        )

    def test_classifier_can_drive_hybrid_query(self):
        classification = classify_query(
            "onde o código implementa o que está no handoff"
        )
        self.assertEqual(
            classification.route,
            QueryRoute.HYBRID,
        )

    def test_hybrid_query_searches_all_three_candidate_spaces(self):
        insert_document(
            self.connection,
            "doc-lexical",
            source_type="DOCUMENTATION",
        )
        insert_document(
            self.connection,
            "doc-text",
            source_type="DOCUMENTATION",
        )
        insert_document(
            self.connection,
            "doc-code",
            source_type="CODE",
        )

        insert_chunk(
            self.connection,
            chunk_id="chunk-lexical",
            document_id="doc-lexical",
            content="handoff explica cancelamento",
            source_type="DOCUMENTATION",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-text",
            document_id="doc-text",
            content="documentação sem termo alvo",
            source_type="DOCUMENTATION",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-code",
            document_id="doc-code",
            content="void CancelCurrent() {}",
            source_type="CODE",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        text_other = [0.0, 1.0] + [0.0] * (
            TEXT_EMBEDDING_DIMENSION - 2
        )
        code_other = [0.0, 1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 2
        )

        upsert_vector_chunk(
            self.vector_client,
            collection_name=TEXT_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-lexical",
            vector=text_other,
            payload=payload(
                document_id="doc-lexical",
                content="handoff explica cancelamento",
                source_type=SourceType.DOCUMENTATION.value,
            ),
        )
        upsert_vector_chunk(
            self.vector_client,
            collection_name=TEXT_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-text",
            vector=self.text_query_vector,
            payload=payload(
                document_id="doc-text",
                content="documentação sem termo alvo",
                source_type=SourceType.DOCUMENTATION.value,
            ),
        )
        upsert_vector_chunk(
            self.vector_client,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-code",
            vector=self.code_query_vector,
            payload=payload(
                document_id="doc-code",
                content="void CancelCurrent() {}",
                source_type=SourceType.CODE.value,
            ),
        )
        upsert_vector_chunk(
            self.vector_client,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-code-other",
            vector=code_other,
            payload=payload(
                document_id="doc-code-other",
                content="void Other() {}",
                source_type=SourceType.CODE.value,
            ),
        )

        query = SearchQuery(
            query="handoff explica cancelamento",
            project_id="codebridge",
            top_k=5,
        )

        result = collect_hybrid_query_candidates(
            self.connection,
            self.vector_client,
            query,
            route=QueryRoute.HYBRID,
            text_query_vector=self.text_query_vector,
            code_query_vector=self.code_query_vector,
        )

        self.assertIsInstance(result, HybridQueryCandidates)
        self.assertEqual(result.route, QueryRoute.HYBRID)
        self.assertEqual(
            [item.chunk_id for item in result.lexical],
            ["chunk-lexical"],
        )
        self.assertEqual(
            result.text_vector[0].chunk_id,
            "chunk-text",
        )
        self.assertEqual(
            result.code_vector[0].chunk_id,
            "chunk-code",
        )

    def test_non_hybrid_route_is_rejected(self):
        query = SearchQuery(
            query="handoff",
            project_id="codebridge",
        )

        with self.assertRaises(ValueError):
            collect_hybrid_query_candidates(
                self.connection,
                self.vector_client,
                query,
                route=QueryRoute.TEXT,
                text_query_vector=self.text_query_vector,
                code_query_vector=self.code_query_vector,
            )

    def test_project_namespace_applies_to_both_vector_spaces(self):
        for project_id in ("codebridge", "drones"):
            upsert_vector_chunk(
                self.vector_client,
                collection_name=TEXT_VECTOR_COLLECTION,
                project_id=project_id,
                chunk_id=f"text-{project_id}",
                vector=self.text_query_vector,
                payload=payload(
                    document_id=f"doc-text-{project_id}",
                    content=project_id,
                    source_type=SourceType.DOCUMENTATION.value,
                ),
            )
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id=project_id,
                chunk_id=f"code-{project_id}",
                vector=self.code_query_vector,
                payload=payload(
                    document_id=f"doc-code-{project_id}",
                    content=project_id,
                    source_type=SourceType.CODE.value,
                ),
            )

        query = SearchQuery(
            query="project",
            project_id="codebridge",
            top_k=10,
        )
        result = collect_hybrid_query_candidates(
            self.connection,
            self.vector_client,
            query,
            route=QueryRoute.HYBRID,
            text_query_vector=self.text_query_vector,
            code_query_vector=self.code_query_vector,
        )

        self.assertEqual(
            [item.chunk_id for item in result.text_vector],
            ["text-codebridge"],
        )
        self.assertEqual(
            [item.chunk_id for item in result.code_vector],
            ["code-codebridge"],
        )

    def test_dimension_validation_is_delegated_to_each_space(self):
        query = SearchQuery(
            query="hybrid",
            project_id="codebridge",
        )

        with self.assertRaises(ValueError):
            collect_hybrid_query_candidates(
                self.connection,
                self.vector_client,
                query,
                route=QueryRoute.HYBRID,
                text_query_vector=[1.0, 0.0],
                code_query_vector=self.code_query_vector,
            )

        with self.assertRaises(ValueError):
            collect_hybrid_query_candidates(
                self.connection,
                self.vector_client,
                query,
                route=QueryRoute.HYBRID,
                text_query_vector=self.text_query_vector,
                code_query_vector=[1.0, 0.0],
            )


if __name__ == "__main__":
    unittest.main()
