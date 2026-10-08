import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.sqlite_schema import connect_rag_index
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.search_service import (
    RagSearchIndexUnavailableError,
    search_context,
)


class RagSearchServiceTests(unittest.TestCase):
    def make_index(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "rag.sqlite3"
        connection = connect_rag_index(path)
        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES (
                'doc-1',
                'codebridge',
                'CODE',
                'source'
            )
            """
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
                path,
                git_branch
            ) VALUES (
                'chunk-1',
                'doc-1',
                'codebridge',
                0,
                'onde controla cancelamento do runtime',
                'CODE',
                'src/runtime.py',
                'main'
            )
            """
        )
        connection.commit()
        initialize_fts5(connection)
        connection.close()
        return path

    def test_non_lexical_query_falls_back_explicitly_to_fts5(self):
        path = self.make_index()

        result = search_context(
            query="onde controla cancelamento do runtime",
            project_id="codebridge",
            sqlite_path=path,
        )

        self.assertEqual(result.requested_route, QueryRoute.CODE)
        self.assertEqual(result.effective_route, QueryRoute.LEXICAL_ONLY)
        self.assertEqual(
            result.fallback_reason,
            "SEMANTIC_EXECUTOR_UNAVAILABLE",
        )
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].chunk_id, "chunk-1")

    def test_semantic_executor_is_used_when_registered(self):
        path = self.make_index()
        calls = []

        def executor(query, route):
            calls.append((query, route))
            return (
                SearchResult(
                    chunk_id="semantic-1",
                    document_id="doc-semantic",
                    content="semantic result",
                    metadata=SourceMetadata(
                        project_id="codebridge",
                        source_type=SourceType.CODE,
                    ),
                    score=0.99,
                    rank=1,
                    retrieval_modes=("TEST_SEMANTIC",),
                ),
            )

        result = search_context(
            query="onde controla cancelamento do runtime",
            project_id="codebridge",
            sqlite_path=path,
            semantic_executor=executor,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], QueryRoute.CODE)
        self.assertEqual(result.requested_route, QueryRoute.CODE)
        self.assertEqual(result.effective_route, QueryRoute.CODE)
        self.assertIsNone(result.fallback_reason)
        self.assertEqual(result.results[0].chunk_id, "semantic-1")

    def test_source_type_path_and_branch_filters_are_forwarded(self):
        path = self.make_index()

        result = search_context(
            query="onde controla cancelamento do runtime",
            project_id="codebridge",
            source_types=("CODE",),
            path_filter="src/",
            branch="main",
            sqlite_path=path,
        )

        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].metadata.path, "src/runtime.py")

        wrong_branch = search_context(
            query="onde controla cancelamento do runtime",
            project_id="codebridge",
            source_types=("CODE",),
            branch="other",
            sqlite_path=path,
        )
        self.assertEqual(wrong_branch.results, ())

    def test_top_k_is_validated_by_search_query(self):
        path = self.make_index()
        with self.assertRaises(ValueError):
            search_context(
                query="x",
                project_id="codebridge",
                top_k=0,
                sqlite_path=path,
            )

    def test_invalid_source_type_is_rejected(self):
        path = self.make_index()
        with self.assertRaises(ValueError):
            search_context(
                query="x",
                project_id="codebridge",
                source_types=("INVALID",),
                sqlite_path=path,
            )

    def test_missing_index_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RagSearchIndexUnavailableError):
                search_context(
                    query="x",
                    project_id="codebridge",
                    sqlite_path=Path(td) / "missing.sqlite3",
                )


if __name__ == "__main__":
    unittest.main()
