import unittest

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.ranking.rrf import DEFAULT_RRF_K, reciprocal_rank_fusion


def result(
    chunk_id,
    *,
    document_id=None,
    content=None,
    rank=1,
    score=1.0,
    mode="TEST",
):
    doc_id = document_id or f"doc-{chunk_id}"
    body = content or f"content-{chunk_id}"
    return SearchResult(
        chunk_id=chunk_id,
        document_id=doc_id,
        content=body,
        metadata=SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path=f"src/{doc_id}.py",
        ),
        score=score,
        rank=rank,
        retrieval_modes=(mode,),
        stale=False,
    )


class RagReciprocalRankFusionTests(unittest.TestCase):
    def test_default_k_is_frozen(self):
        self.assertEqual(DEFAULT_RRF_K, 60)

    def test_chunk_present_in_multiple_rankings_rises(self):
        lexical = (
            result("a", rank=1, mode="LEX"),
            result("shared", rank=2, mode="LEX"),
        )
        text = (
            result("shared", rank=1, mode="TEXT"),
            result("b", rank=2, mode="TEXT"),
        )
        code = (
            result("shared", rank=1, mode="CODE"),
            result("c", rank=2, mode="CODE"),
        )

        fused = reciprocal_rank_fusion(
            (lexical, text, code)
        )

        self.assertEqual(fused[0].chunk_id, "shared")
        self.assertEqual(
            fused[0].retrieval_modes,
            ("LEX", "TEXT", "CODE"),
        )
        expected = (
            1 / (60 + 2)
            + 1 / (60 + 1)
            + 1 / (60 + 1)
        )
        self.assertAlmostEqual(fused[0].score, expected)

    def test_input_scores_do_not_affect_rrf(self):
        first = (
            result("a", rank=1, score=-9999, mode="LEX"),
            result("b", rank=2, score=9999, mode="LEX"),
        )

        fused = reciprocal_rank_fusion((first,))

        self.assertEqual(
            [item.chunk_id for item in fused],
            ["a", "b"],
        )

    def test_tie_break_is_deterministic_by_chunk_id(self):
        ranking_a = (result("b", mode="A"),)
        ranking_b = (result("a", mode="B"),)

        fused = reciprocal_rank_fusion(
            (ranking_a, ranking_b)
        )

        self.assertEqual(
            [item.chunk_id for item in fused],
            ["a", "b"],
        )
        self.assertEqual(
            [item.rank for item in fused],
            [1, 2],
        )

    def test_exact_duplicate_inside_same_ranking_counts_once(self):
        duplicated = (
            result("a", rank=1, mode="LEX"),
            result("a", rank=2, mode="LEX"),
        )

        fused = reciprocal_rank_fusion((duplicated,))

        self.assertEqual(len(fused), 1)
        self.assertAlmostEqual(
            fused[0].score,
            1 / (60 + 1),
        )

    def test_near_duplicate_content_is_not_collapsed(self):
        ranking = (
            result(
                "chunk-1",
                content="same conceptual content",
                mode="LEX",
            ),
            result(
                "chunk-2",
                content="same conceptual content",
                mode="LEX",
            ),
        )

        fused = reciprocal_rank_fusion((ranking,))

        self.assertEqual(len(fused), 2)

    def test_conflicting_same_chunk_content_is_rejected(self):
        left = result(
            "shared",
            document_id="doc-shared",
            content="alpha",
            mode="LEX",
        )
        right = result(
            "shared",
            document_id="doc-shared",
            content="beta",
            mode="TEXT",
        )

        with self.assertRaises(ValueError):
            reciprocal_rank_fusion(
                ((left,), (right,))
            )

    def test_top_k_truncates_after_fusion(self):
        ranking = tuple(
            result(f"chunk-{index}", rank=index)
            for index in range(1, 6)
        )

        fused = reciprocal_rank_fusion(
            (ranking,),
            top_k=2,
        )

        self.assertEqual(len(fused), 2)
        self.assertEqual(
            [item.chunk_id for item in fused],
            ["chunk-1", "chunk-2"],
        )

    def test_empty_rankings_return_empty_tuple(self):
        self.assertEqual(
            reciprocal_rank_fusion(((), (), ())),
            (),
        )

    def test_invalid_k_and_top_k_are_rejected(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion((), k=0)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion((), top_k=0)

    def test_non_search_result_is_rejected(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion((("bad",),))


if __name__ == "__main__":
    unittest.main()
