import unittest

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.ranking.dedup import (
    NEAR_DUPLICATE_JACCARD_THRESHOLD,
    DeduplicationOutcome,
    deduplicate_ranked_results,
)


def hit(chunk_id, content, rank, score=None):
    return SearchResult(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        content=content,
        metadata=SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
        ),
        score=float(score if score is not None else 1.0 / rank),
        rank=rank,
        retrieval_modes=("RRF",),
        stale=False,
    )


class RagDeduplicationTests(unittest.TestCase):
    def test_threshold_is_frozen(self):
        self.assertEqual(NEAR_DUPLICATE_JACCARD_THRESHOLD, 0.90)

    def test_normalized_exact_duplicate_is_suppressed(self):
        outcome = deduplicate_ranked_results(
            (
                hit("a", "Cancel Current Request", 1),
                hit("b", " cancel-current   request ", 2),
            )
        )
        self.assertEqual([x.chunk_id for x in outcome.results], ["a"])
        self.assertEqual(len(outcome.suppressed), 1)
        self.assertEqual(
            outcome.suppressed[0].reason,
            "NORMALIZED_EXACT",
        )
        self.assertEqual(
            outcome.suppressed[0].kept_chunk_id,
            "a",
        )

    def test_near_duplicate_long_chunk_is_suppressed(self):
        base = (
            "the runtime validates cancellation before sending the request "
            "to the worker and records the execution state for auditing"
        )
        near = (
            "the runtime validates cancellation before sending the request "
            "to the worker and records the execution state for audit"
        )
        outcome = deduplicate_ranked_results(
            (
                hit("a", base, 1),
                hit("b", near, 2),
            ),
            threshold=0.80,
        )
        self.assertEqual([x.chunk_id for x in outcome.results], ["a"])
        self.assertEqual(
            outcome.suppressed[0].reason,
            "TOKEN_SHINGLE_JACCARD",
        )

    def test_short_similar_chunks_are_not_overcollapsed(self):
        outcome = deduplicate_ranked_results(
            (
                hit("a", "cancel request now", 1),
                hit("b", "cancel request later", 2),
            )
        )
        self.assertEqual(
            [x.chunk_id for x in outcome.results],
            ["a", "b"],
        )

    def test_distinct_chunks_remain(self):
        outcome = deduplicate_ranked_results(
            (
                hit("a", "alpha beta gamma delta", 1),
                hit("b", "one two three four", 2),
            )
        )
        self.assertEqual(len(outcome.results), 2)
        self.assertEqual(outcome.suppressed, ())

    def test_first_ranked_representation_wins(self):
        outcome = deduplicate_ranked_results(
            (
                hit("high", "same content here", 1, score=9.0),
                hit("low", "same content here", 2, score=8.0),
            )
        )
        self.assertEqual(outcome.results[0].chunk_id, "high")
        self.assertEqual(outcome.results[0].score, 9.0)

    def test_ranks_are_compacted_after_suppression(self):
        outcome = deduplicate_ranked_results(
            (
                hit("a", "same content here", 1),
                hit("b", "same content here", 2),
                hit("c", "completely different result", 3),
            )
        )
        self.assertEqual(
            [x.chunk_id for x in outcome.results],
            ["a", "c"],
        )
        self.assertEqual(
            [x.rank for x in outcome.results],
            [1, 2],
        )

    def test_top_k_is_applied_after_deduplication(self):
        outcome = deduplicate_ranked_results(
            (
                hit("a", "same content here", 1),
                hit("b", "same content here", 2),
                hit("c", "distinct result c", 3),
                hit("d", "distinct result d", 4),
            ),
            top_k=2,
        )
        self.assertEqual(
            [x.chunk_id for x in outcome.results],
            ["a", "c"],
        )

    def test_outcome_is_structured(self):
        outcome = deduplicate_ranked_results(
            (hit("a", "alpha", 1),)
        )
        self.assertIsInstance(outcome, DeduplicationOutcome)

    def test_invalid_options_are_rejected(self):
        with self.assertRaises(ValueError):
            deduplicate_ranked_results((), threshold=1.1)
        with self.assertRaises(ValueError):
            deduplicate_ranked_results((), min_tokens=0)
        with self.assertRaises(ValueError):
            deduplicate_ranked_results((), shingle_size=0)
        with self.assertRaises(ValueError):
            deduplicate_ranked_results((), top_k=0)

    def test_non_search_result_is_rejected(self):
        with self.assertRaises(ValueError):
            deduplicate_ranked_results(("bad",))


if __name__ == "__main__":
    unittest.main()
