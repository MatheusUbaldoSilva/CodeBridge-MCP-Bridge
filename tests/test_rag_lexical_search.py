import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_search import (
    LexicalSearchHit,
    RagLexicalQueryError,
    search_lexical,
)
from rag.index.sqlite_schema import connect_rag_index


def insert_document(
    connection,
    document_id,
    *,
    project_id="project-a",
    source_type="CODE",
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
    project_id="project-a",
    ordinal=0,
    content,
    source_type="CODE",
    path=None,
    symbol=None,
    git_message=None,
    title=None,
    heading_path=None,
    branch=None,
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
            path,
            symbol,
            git_message,
            title,
            heading_path,
            git_branch
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            document_id,
            project_id,
            ordinal,
            content,
            source_type,
            path,
            symbol,
            git_message,
            title,
            heading_path,
            branch,
        ),
    )


class RagLexicalSearchTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_rag_index(":memory:")
        self.addCleanup(self.connection.close)

        insert_document(
            self.connection,
            "doc-move",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-move",
            document_id="doc-move",
            content="movement provenance helper",
            symbol="GetMoveSpeedProvenance",
            path="src/movement.cpp",
        )

        insert_document(
            self.connection,
            "doc-wait",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-wait",
            document_id="doc-wait",
            content="MCP wait tool implementation",
            symbol="codebridge_wait",
            path="author_mcp/mcp_server.py",
        )

        insert_document(
            self.connection,
            "doc-exec",
            source_type="EXECUTION",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-exec",
            document_id="doc-exec",
            content="wait contract marker EXECUTION_V2_WAIT",
            source_type="EXECUTION",
            git_message="test EXECUTION_V2_WAIT contract",
            title="Execution wait contract",
        )

        insert_document(
            self.connection,
            "doc-other-project",
            project_id="project-b",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-other-project",
            document_id="doc-other-project",
            project_id="project-b",
            content="GetMoveSpeedProvenance",
            symbol="GetMoveSpeedProvenance",
        )

        self.connection.commit()
        initialize_fts5(self.connection)

    def search(self, text, **kwargs):
        return search_lexical(
            self.connection,
            SearchQuery(
                query=text,
                project_id=kwargs.pop(
                    "project_id",
                    "project-a",
                ),
                **kwargs,
            ),
        )

    def test_exact_get_move_speed_provenance_query(self):
        hits = self.search(
            "GetMoveSpeedProvenance"
        )
        self.assertEqual(
            [hit.chunk_id for hit in hits],
            ["chunk-move"],
        )

    def test_exact_codebridge_wait_query(self):
        hits = self.search("codebridge_wait")
        self.assertEqual(
            [hit.chunk_id for hit in hits],
            ["chunk-wait"],
        )

    def test_exact_execution_v2_wait_query(self):
        hits = self.search("EXECUTION_V2_WAIT")
        self.assertEqual(
            [hit.chunk_id for hit in hits],
            ["chunk-exec"],
        )

    def test_project_scope_is_mandatory_and_isolated(self):
        hits_a = self.search(
            "GetMoveSpeedProvenance",
            project_id="project-a",
        )
        hits_b = self.search(
            "GetMoveSpeedProvenance",
            project_id="project-b",
        )

        self.assertEqual(
            [item.chunk_id for item in hits_a],
            ["chunk-move"],
        )
        self.assertEqual(
            [item.chunk_id for item in hits_b],
            ["chunk-other-project"],
        )

    def test_source_type_filter_is_applied_relationally(self):
        self.assertEqual(
            self.search(
                "EXECUTION_V2_WAIT",
                source_types=(SourceType.CODE,),
            ),
            (),
        )
        self.assertEqual(
            [
                item.chunk_id
                for item in self.search(
                    "EXECUTION_V2_WAIT",
                    source_types=(SourceType.EXECUTION,),
                )
            ],
            ["chunk-exec"],
        )

    def test_path_filter_is_literal_substring_not_sql_wildcard(self):
        hits = self.search(
            "codebridge_wait",
            path_filter="author_mcp/mcp_",
        )
        self.assertEqual(
            [item.chunk_id for item in hits],
            ["chunk-wait"],
        )

        self.assertEqual(
            self.search(
                "codebridge_wait",
                path_filter="author_mcp/%",
            ),
            (),
        )

    def test_windows_path_filter_is_normalized(self):
        hits = self.search(
            "codebridge_wait",
            path_filter=r"author_mcp\mcp_server",
        )
        self.assertEqual(
            [item.chunk_id for item in hits],
            ["chunk-wait"],
        )

    def test_branch_filter_is_exact(self):
        insert_document(
            self.connection,
            "doc-branch",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-branch",
            document_id="doc-branch",
            content="BranchSpecificMarker",
            branch="rag-005-sqlite-fts",
        )
        self.connection.commit()

        self.assertEqual(
            [
                item.chunk_id
                for item in self.search(
                    "BranchSpecificMarker",
                    branch="rag-005-sqlite-fts",
                )
            ],
            ["chunk-branch"],
        )
        self.assertEqual(
            self.search(
                "BranchSpecificMarker",
                branch="main",
            ),
            (),
        )

    def test_raw_fts_operators_are_treated_as_literal_phrase(self):
        insert_document(
            self.connection,
            "doc-operators",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-operators",
            document_id="doc-operators",
            content="alpha OR beta",
        )
        self.connection.commit()

        hits = self.search("alpha OR beta")
        self.assertEqual(
            [item.chunk_id for item in hits],
            ["chunk-operators"],
        )

    def test_double_quotes_do_not_escape_into_raw_fts_syntax(self):
        insert_document(
            self.connection,
            "doc-quote",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-quote",
            document_id="doc-quote",
            content='quoted marker alpha "beta" gamma',
        )
        self.connection.commit()

        hits = self.search('alpha "beta" gamma')
        self.assertEqual(
            [item.chunk_id for item in hits],
            ["chunk-quote"],
        )

    def test_punctuation_only_query_is_rejected(self):
        with self.assertRaises(RagLexicalQueryError):
            self.search("---")

    def test_empty_optional_filters_are_rejected(self):
        with self.assertRaises(RagLexicalQueryError):
            self.search(
                "codebridge_wait",
                path_filter="   ",
            )

        with self.assertRaises(RagLexicalQueryError):
            self.search(
                "codebridge_wait",
                branch="   ",
            )

    def test_top_k_is_honored_without_relevance_policy(self):
        for index in range(3):
            document_id = f"doc-limit-{index}"
            insert_document(
                self.connection,
                document_id,
            )
            insert_chunk(
                self.connection,
                chunk_id=f"chunk-limit-{index}",
                document_id=document_id,
                content="TopKMarker",
            )
        self.connection.commit()

        hits = self.search(
            "TopKMarker",
            top_k=2,
        )
        self.assertEqual(len(hits), 2)

    def test_result_order_is_deterministic_relational_order(self):
        for document_id, chunk_id in (
            ("doc-z", "chunk-z"),
            ("doc-a", "chunk-a"),
        ):
            insert_document(
                self.connection,
                document_id,
            )
            insert_chunk(
                self.connection,
                chunk_id=chunk_id,
                document_id=document_id,
                content="OrderMarker",
            )
        self.connection.commit()

        first = self.search("OrderMarker")
        second = self.search("OrderMarker")

        self.assertEqual(first, second)
        self.assertEqual(
            [item.chunk_id for item in first],
            ["chunk-a", "chunk-z"],
        )

    def test_hit_preserves_source_metadata(self):
        hits = self.search("GetMoveSpeedProvenance")
        hit = hits[0]

        self.assertIsInstance(
            hit,
            LexicalSearchHit,
        )
        self.assertEqual(
            hit.metadata.project_id,
            "project-a",
        )
        self.assertEqual(
            hit.metadata.source_type,
            SourceType.CODE,
        )
        self.assertEqual(
            hit.metadata.path,
            "src/movement.cpp",
        )
        self.assertEqual(
            hit.metadata.symbol,
            "GetMoveSpeedProvenance",
        )

    def test_no_score_or_rank_is_published_in_005_c(self):
        hit = self.search(
            "GetMoveSpeedProvenance"
        )[0]

        self.assertFalse(hasattr(hit, "score"))
        self.assertFalse(hasattr(hit, "rank"))

    def test_fts_must_be_initialized_explicitly(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        with self.assertRaises(RuntimeError):
            search_lexical(
                connection,
                SearchQuery(
                    query="anything",
                    project_id="project-a",
                ),
            )

    def test_no_bm25_ranking_is_implemented_in_search_module(self):
        import rag.index.lexical_search as module

        source = Path(
            module.__file__
        ).read_text(encoding="utf-8").lower()

        self.assertNotIn("bm25(", source)
        self.assertFalse(
            hasattr(LexicalSearchHit, "score")
        )
        self.assertFalse(
            hasattr(LexicalSearchHit, "rank")
        )


if __name__ == "__main__":
    unittest.main()
