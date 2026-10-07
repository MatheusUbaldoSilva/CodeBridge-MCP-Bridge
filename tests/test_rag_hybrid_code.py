import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import upsert_vector_chunk
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.retrieval.hybrid_code import (
    CODE_VECTOR_RETRIEVAL_MODE,
    collect_code_hybrid_candidates,
    search_code_vector,
)


def insert_document(connection, document_id, project_id="codebridge"):
    connection.execute(
        """
        INSERT INTO rag_documents (
            document_id,
            project_id,
            source_type,
            content
        ) VALUES (?, ?, 'CODE', 'source')
        """,
        (document_id, project_id),
    )


def insert_chunk(
    connection,
    *,
    chunk_id,
    document_id,
    content,
    project_id="codebridge",
    path=None,
):
    connection.execute(
        """
        INSERT INTO rag_chunks (
            chunk_id,
            document_id,
            project_id,
            ordinal,
            content,
            source_type,
            path
        ) VALUES (?, ?, ?, 0, ?, 'CODE', ?)
        """,
        (
            chunk_id,
            document_id,
            project_id,
            content,
            path,
        ),
    )


def vector_payload(
    *,
    document_id,
    content,
    path=None,
):
    return {
        "document_id": document_id,
        "content": content,
        "source_type": SourceType.CODE.value,
        "path": path,
    }


class RagHybridCodeCandidatesTests(unittest.TestCase):
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

    def test_vector_text_search_returns_search_results(self):
        vector = [1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 1
        )
        upsert_vector_chunk(
            self.vector_client,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-vector",
            vector=vector,
            payload=vector_payload(
                document_id="doc-vector",
                content="controle por embedding",
                path="docs/vector.md",
            ),
        )

        results = search_code_vector(
            self.vector_client,
            SearchQuery(
                query="controle",
                project_id="codebridge",
                top_k=5,
            ),
            vector,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, "chunk-vector")
        self.assertEqual(
            results[0].retrieval_modes,
            (CODE_VECTOR_RETRIEVAL_MODE,),
        )
        self.assertEqual(results[0].rank, 1)

    def test_project_namespace_is_enforced(self):
        vector = [1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 1
        )
        for project, chunk in (
            ("codebridge", "chunk-cb"),
            ("drones", "chunk-dr"),
        ):
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id=project,
                chunk_id=chunk,
                vector=vector,
                payload=vector_payload(
                    document_id=f"doc-{project}",
                    content=project,
                ),
            )

        results = search_code_vector(
            self.vector_client,
            SearchQuery(
                query="anything",
                project_id="codebridge",
                top_k=10,
            ),
            vector,
        )

        self.assertEqual(
            [item.chunk_id for item in results],
            ["chunk-cb"],
        )

    def test_path_filter_matches_lexical_substring_semantics(self):
        vector = [1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 1
        )
        for point_id, path in (
            ("chunk-a", "docs/guide.md"),
            ("chunk-b", "src/internal.txt"),
        ):
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id="codebridge",
                chunk_id=point_id,
                vector=vector,
                payload=vector_payload(
                    document_id=f"doc-{point_id}",
                    content=point_id,
                    path=path,
                ),
            )

        results = search_code_vector(
            self.vector_client,
            SearchQuery(
                query="anything",
                project_id="codebridge",
                path_filter="docs/",
                top_k=10,
            ),
            vector,
        )

        self.assertEqual(
            [item.chunk_id for item in results],
            ["chunk-a"],
        )

    def test_collect_combines_candidate_sets_without_fusing(self):
        insert_document(self.connection, "doc-lexical")
        insert_document(self.connection, "doc-vector")
        insert_chunk(
            self.connection,
            chunk_id="chunk-lexical",
            document_id="doc-lexical",
            content="cancelamento controlado pelo FTS5",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-vector",
            document_id="doc-vector",
            content="fila sem termo lexical alvo",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        lexical_vector = [0.0, 1.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 2
        )
        semantic_vector = [1.0, 0.0] + [0.0] * (
            CODE_EMBEDDING_DIMENSION - 2
        )

        upsert_vector_chunk(
            self.vector_client,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-lexical",
            vector=lexical_vector,
            payload=vector_payload(
                document_id="doc-lexical",
                content="cancelamento controlado pelo FTS5",
            ),
        )
        upsert_vector_chunk(
            self.vector_client,
            collection_name=CODE_VECTOR_COLLECTION,
            project_id="codebridge",
            chunk_id="chunk-vector",
            vector=semantic_vector,
            payload=vector_payload(
                document_id="doc-vector",
                content="fila sem termo lexical alvo",
            ),
        )

        candidates = collect_code_hybrid_candidates(
            self.connection,
            self.vector_client,
            SearchQuery(
                query="cancelamento",
                project_id="codebridge",
                top_k=5,
            ),
            semantic_vector,
        )

        self.assertEqual(
            [item.chunk_id for item in candidates.lexical],
            ["chunk-lexical"],
        )
        self.assertEqual(
            candidates.vector[0].chunk_id,
            "chunk-vector",
        )
        self.assertIn(
            "chunk-lexical",
            [item.chunk_id for item in candidates.vector],
        )

        self.assertEqual(
            candidates.lexical[0].retrieval_modes,
            ("LEXICAL_FTS5_BM25",),
        )
        self.assertEqual(
            candidates.vector[0].retrieval_modes,
            (CODE_VECTOR_RETRIEVAL_MODE,),
        )

    def test_wrong_query_vector_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            search_code_vector(
                self.vector_client,
                SearchQuery(
                    query="x",
                    project_id="codebridge",
                ),
                [1.0, 0.0],
            )


if __name__ == "__main__":
    unittest.main()
