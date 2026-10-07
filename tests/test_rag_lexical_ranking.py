import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.contracts import SearchQuery, SearchResult, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import (
    LEXICAL_BM25_WEIGHTS,
    LEXICAL_RETRIEVAL_MODE,
    lexical_score_from_bm25,
    search_lexical_ranked,
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
    content="",
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


class RagLexicalRankingTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_rag_index(":memory:")
        self.addCleanup(self.connection.close)

    def ranked(self, text, **kwargs):
        return search_lexical_ranked(
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

    def test_weights_are_frozen_in_fts_column_order(self):
        self.assertEqual(
            LEXICAL_BM25_WEIGHTS,
            (
                0.0,
                0.0,
                0.0,
                1.0,
                3.0,
                6.0,
                2.0,
                4.0,
                3.0,
            ),
        )

    def test_public_score_is_negative_bm25_distance(self):
        self.assertEqual(
            lexical_score_from_bm25(-2.5),
            2.5,
        )
        self.assertEqual(
            lexical_score_from_bm25(1.25),
            -1.25,
        )
        self.assertTrue(
            math.isfinite(
                lexical_score_from_bm25(-0.0001)
            )
        )

    def test_non_finite_bm25_is_rejected(self):
        for value in (
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    lexical_score_from_bm25(value)

    def test_symbol_match_outranks_title_and_content(self):
        for document_id in (
            "doc-symbol",
            "doc-title",
            "doc-content",
        ):
            insert_document(
                self.connection,
                document_id,
            )

        insert_chunk(
            self.connection,
            chunk_id="chunk-symbol",
            document_id="doc-symbol",
            content="neutral text",
            symbol="RankMarker",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-title",
            document_id="doc-title",
            content="neutral text",
            title="RankMarker",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-content",
            document_id="doc-content",
            content="RankMarker",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        results = self.ranked("RankMarker")

        self.assertEqual(
            [item.chunk_id for item in results],
            [
                "chunk-symbol",
                "chunk-title",
                "chunk-content",
            ],
        )
        self.assertGreater(
            results[0].score,
            results[1].score,
        )
        self.assertGreater(
            results[1].score,
            results[2].score,
        )

    def test_path_and_heading_have_same_frozen_weight(self):
        self.assertEqual(
            LEXICAL_BM25_WEIGHTS[4],
            LEXICAL_BM25_WEIGHTS[8],
        )
        self.assertEqual(
            LEXICAL_BM25_WEIGHTS[4],
            3.0,
        )

    def test_equal_bm25_scores_use_stable_tiebreak(self):
        for document_id in (
            "doc-b",
            "doc-a",
        ):
            insert_document(
                self.connection,
                document_id,
            )
            insert_chunk(
                self.connection,
                chunk_id=f"chunk-{document_id}",
                document_id=document_id,
                content="TieMarker",
            )

        self.connection.commit()
        initialize_fts5(self.connection)

        results = self.ranked("TieMarker")

        self.assertEqual(
            [item.chunk_id for item in results],
            [
                "chunk-doc-a",
                "chunk-doc-b",
            ],
        )
        self.assertAlmostEqual(
            results[0].score,
            results[1].score,
        )

    def test_rank_is_one_based_final_position(self):
        for index in range(3):
            document_id = f"doc-{index}"
            insert_document(
                self.connection,
                document_id,
            )
            insert_chunk(
                self.connection,
                chunk_id=f"chunk-{index}",
                document_id=document_id,
                content="SameMarker",
            )

        self.connection.commit()
        initialize_fts5(self.connection)

        results = self.ranked("SameMarker")

        self.assertEqual(
            [item.rank for item in results],
            [1, 2, 3],
        )

    def test_results_use_stable_search_result_contract(self):
        insert_document(
            self.connection,
            "doc",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk",
            document_id="doc",
            content="ContractMarker",
            path="src/runtime.py",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        result = self.ranked(
            "ContractMarker"
        )[0]

        self.assertIsInstance(
            result,
            SearchResult,
        )
        self.assertEqual(
            result.retrieval_modes,
            (LEXICAL_RETRIEVAL_MODE,),
        )
        self.assertFalse(result.stale)
        self.assertEqual(
            result.metadata.path,
            "src/runtime.py",
        )

    def test_project_scope_still_prevents_cross_project_results(self):
        insert_document(
            self.connection,
            "doc-a",
            project_id="project-a",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-a",
            document_id="doc-a",
            project_id="project-a",
            content="ScopeMarker",
        )

        insert_document(
            self.connection,
            "doc-b",
            project_id="project-b",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-b",
            document_id="doc-b",
            project_id="project-b",
            content="ScopeMarker",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        self.assertEqual(
            [
                item.chunk_id
                for item in self.ranked(
                    "ScopeMarker",
                    project_id="project-a",
                )
            ],
            ["chunk-a"],
        )

    def test_source_path_branch_and_top_k_filters_remain_effective(self):
        for document_id in (
            "doc-code",
            "doc-exec",
        ):
            insert_document(
                self.connection,
                document_id,
                source_type=(
                    "EXECUTION"
                    if document_id == "doc-exec"
                    else "CODE"
                ),
            )

        insert_chunk(
            self.connection,
            chunk_id="chunk-code",
            document_id="doc-code",
            content="FilterMarker",
            path="src/runtime.py",
            branch="main",
        )
        insert_chunk(
            self.connection,
            chunk_id="chunk-exec",
            document_id="doc-exec",
            content="FilterMarker",
            source_type="EXECUTION",
            path="audit/run.txt",
            branch="audit",
        )
        self.connection.commit()
        initialize_fts5(self.connection)

        results = self.ranked(
            "FilterMarker",
            source_types=(SourceType.CODE,),
            path_filter="src/runtime",
            branch="main",
            top_k=1,
        )
        self.assertEqual(
            [item.chunk_id for item in results],
            ["chunk-code"],
        )

    def test_handoff_queries_receive_score_and_rank(self):
        for document_id, marker, symbol, source_type in (
            (
                "doc-move",
                "movement provenance helper",
                "GetMoveSpeedProvenance",
                "CODE",
            ),
            (
                "doc-wait",
                "MCP wait tool",
                "codebridge_wait",
                "CODE",
            ),
            (
                "doc-exec",
                "EXECUTION_V2_WAIT",
                None,
                "EXECUTION",
            ),
        ):
            insert_document(
                self.connection,
                document_id,
                source_type=source_type,
            )
            insert_chunk(
                self.connection,
                chunk_id=f"chunk-{document_id}",
                document_id=document_id,
                content=marker,
                symbol=symbol,
                source_type=source_type,
            )

        self.connection.commit()
        initialize_fts5(self.connection)

        for query in (
            "GetMoveSpeedProvenance",
            "codebridge_wait",
            "EXECUTION_V2_WAIT",
        ):
            with self.subTest(query=query):
                results = self.ranked(query)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].rank, 1)
                self.assertTrue(
                    math.isfinite(results[0].score)
                )

    def test_ranking_is_deterministic(self):
        for document_id in (
            "doc-a",
            "doc-b",
        ):
            insert_document(
                self.connection,
                document_id,
            )
            insert_chunk(
                self.connection,
                chunk_id=f"chunk-{document_id}",
                document_id=document_id,
                content="DeterministicMarker",
            )

        self.connection.commit()
        initialize_fts5(self.connection)

        first = self.ranked(
            "DeterministicMarker"
        )
        second = self.ranked(
            "DeterministicMarker"
        )
        self.assertEqual(first, second)

    def test_no_embedding_or_hybrid_signal_is_used(self):
        import rag.index.lexical_ranking as module

        source = Path(
            module.__file__
        ).read_text(encoding="utf-8").lower()

        self.assertNotIn("embedding", source.replace(
            "embeddings and hybrid fusion remain out of scope.",
            ""
        ))
        self.assertNotIn("vector", source)
        self.assertNotIn("cosine", source)


if __name__ == "__main__":
    unittest.main()
