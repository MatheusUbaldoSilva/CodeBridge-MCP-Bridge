import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import search_lexical_ranked
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
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.runtime.context_service import (
    RagContextSourceMissingError,
    get_context,
)
from rag.runtime.query_classifier import QueryRoute


PROJECT_A = "codebridge"
PROJECT_B = "drones"


def basis(dimension):
    return [1.0] + [0.0] * (dimension - 1)


def insert_source(
    connection,
    *,
    project_id,
    document_id,
    chunk_id,
    source_type,
    content,
    path,
):
    connection.execute(
        """
        INSERT INTO rag_documents (
            document_id,
            project_id,
            source_type,
            content,
            path
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            document_id,
            project_id,
            source_type,
            content,
            path,
        ),
    )
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
        ) VALUES (?, ?, ?, 0, ?, ?, ?)
        """,
        (
            chunk_id,
            document_id,
            project_id,
            content,
            source_type,
            path,
        ),
    )


def vector_payload(document_id, content, source_type, path):
    return {
        "document_id": document_id,
        "content": content,
        "source_type": source_type,
        "path": path,
    }


class Rag015ScopeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.sqlite_path = Path(self.temp.name) / "rag.sqlite3"
        self.connection = connect_rag_index(self.sqlite_path)
        self.addCleanup(self.connection.close)

        shared_text = "shared scope marker identical text"
        shared_code = "def shared_scope_marker(): return True"

        insert_source(
            self.connection,
            project_id=PROJECT_A,
            document_id="doc-a-text",
            chunk_id="chunk-a-text",
            source_type=SourceType.DOCUMENTATION.value,
            content=shared_text,
            path="docs/a.md",
        )
        insert_source(
            self.connection,
            project_id=PROJECT_B,
            document_id="doc-b-text",
            chunk_id="chunk-b-text",
            source_type=SourceType.DOCUMENTATION.value,
            content=shared_text,
            path="docs/b.md",
        )
        insert_source(
            self.connection,
            project_id=PROJECT_A,
            document_id="doc-a-code",
            chunk_id="chunk-a-code",
            source_type=SourceType.CODE.value,
            content=shared_code,
            path="src/a.py",
        )
        insert_source(
            self.connection,
            project_id=PROJECT_B,
            document_id="doc-b-code",
            chunk_id="chunk-b-code",
            source_type=SourceType.CODE.value,
            content=shared_code,
            path="src/b.py",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        self.vector_client = open_qdrant_local(
            Path(self.temp.name) / "qdrant"
        )
        self.addCleanup(
            lambda: close_qdrant_local(self.vector_client)
        )
        ensure_vector_collections(self.vector_client)

        text_vector = basis(TEXT_EMBEDDING_DIMENSION)
        code_vector = basis(CODE_EMBEDDING_DIMENSION)

        for project_id, suffix in (
            (PROJECT_A, "a"),
            (PROJECT_B, "b"),
        ):
            upsert_vector_chunk(
                self.vector_client,
                collection_name=TEXT_VECTOR_COLLECTION,
                project_id=project_id,
                chunk_id=f"chunk-{suffix}-text",
                vector=text_vector,
                payload=vector_payload(
                    f"doc-{suffix}-text",
                    shared_text,
                    SourceType.DOCUMENTATION.value,
                    f"docs/{suffix}.md",
                ),
            )
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id=project_id,
                chunk_id=f"chunk-{suffix}-code",
                vector=code_vector,
                payload=vector_payload(
                    f"doc-{suffix}-code",
                    shared_code,
                    SourceType.CODE.value,
                    f"src/{suffix}.py",
                ),
            )

        self.text_vector = text_vector
        self.code_vector = code_vector

    def test_lexical_scope_never_returns_project_b(self):
        results = search_lexical_ranked(
            self.connection,
            SearchQuery(
                query="shared scope marker",
                project_id=PROJECT_A,
                top_k=20,
            ),
        )

        self.assertTrue(results)
        self.assertTrue(
            all(item.metadata.project_id == PROJECT_A for item in results)
        )
        self.assertNotIn(
            "chunk-b-text",
            {item.chunk_id for item in results},
        )
        self.assertNotIn(
            "chunk-b-code",
            {item.chunk_id for item in results},
        )

    def test_hybrid_scope_filters_both_vector_collections(self):
        result = collect_hybrid_query_candidates(
            self.connection,
            self.vector_client,
            SearchQuery(
                query="shared scope marker",
                project_id=PROJECT_A,
                top_k=20,
            ),
            route=QueryRoute.HYBRID,
            text_query_vector=self.text_vector,
            code_query_vector=self.code_vector,
        )

        for ranking in (
            result.lexical,
            result.text_vector,
            result.code_vector,
        ):
            self.assertTrue(
                all(
                    item.metadata.project_id == PROJECT_A
                    for item in ranking
                )
            )

        ids = {
            item.chunk_id
            for ranking in (
                result.lexical,
                result.text_vector,
                result.code_vector,
            )
            for item in ranking
        }
        self.assertNotIn("chunk-b-text", ids)
        self.assertNotIn("chunk-b-code", ids)
        self.assertIn("chunk-a-text", ids)
        self.assertIn("chunk-a-code", ids)

    def test_project_b_scope_does_not_leak_project_a(self):
        result = collect_hybrid_query_candidates(
            self.connection,
            self.vector_client,
            SearchQuery(
                query="shared scope marker",
                project_id=PROJECT_B,
                top_k=20,
            ),
            route=QueryRoute.HYBRID,
            text_query_vector=self.text_vector,
            code_query_vector=self.code_vector,
        )

        ids = {
            item.chunk_id
            for ranking in (
                result.lexical,
                result.text_vector,
                result.code_vector,
            )
            for item in ranking
        }
        self.assertNotIn("chunk-a-text", ids)
        self.assertNotIn("chunk-a-code", ids)
        self.assertIn("chunk-b-text", ids)
        self.assertIn("chunk-b-code", ids)

    def test_get_context_rejects_cross_project_chunk_id(self):
        with self.assertRaises(RagContextSourceMissingError):
            get_context(
                project_id=PROJECT_A,
                chunk_ids=("chunk-b-text",),
                sqlite_path=self.sqlite_path,
            )

    def test_get_context_returns_same_chunk_for_own_project(self):
        result = get_context(
            project_id=PROJECT_A,
            chunk_ids=("chunk-a-text",),
            sqlite_path=self.sqlite_path,
        )

        self.assertEqual(result.project_id, PROJECT_A)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].project_id, PROJECT_A)
        self.assertEqual(result.items[0].chunk_id, "chunk-a-text")


if __name__ == "__main__":
    unittest.main()
