import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.markdown import chunk_markdown
from rag.chunking.overlap import (
    OverlapReason,
    apply_controlled_overlap,
)
from rag.chunking.text_log import (
    TextLogChunkDraft,
    TextLogChunkKind,
    chunk_text_log,
)


class RagControlledOverlapTests(unittest.TestCase):
    def test_forced_continuation_receives_overlap(self):
        chunks = chunk_text_log(
            "\n".join(str(i) for i in range(1, 17)),
            max_lines=8,
        )
        views = apply_controlled_overlap(
            chunks,
            overlap_lines=3,
        )

        self.assertEqual(len(views), 2)
        self.assertFalse(views[0].overlap_applied)
        self.assertTrue(views[1].overlap_applied)
        self.assertEqual(views[1].overlap_lines, 2)
        self.assertEqual(views[1].overlap_line_start, 7)
        self.assertEqual(views[1].overlap_line_end, 8)
        self.assertEqual(
            views[1].content,
            "7\n8\n9\n10\n11\n12\n13\n14\n15\n16",
        )
        self.assertEqual(
            views[1].reason,
            OverlapReason.FORCED_CONTINUATION,
        )

    def test_overlap_is_capped_by_hard_limit(self):
        chunks = (
            TextLogChunkDraft(
                ordinal=0,
                content="\n".join(str(i) for i in range(1, 21)),
                kind=TextLogChunkKind.BLOCK,
                line_start=1,
                line_end=20,
            ),
            TextLogChunkDraft(
                ordinal=1,
                content="\n".join(str(i) for i in range(21, 41)),
                kind=TextLogChunkKind.BLOCK,
                line_start=21,
                line_end=40,
                continuation=True,
            ),
        )
        views = apply_controlled_overlap(
            chunks,
            overlap_lines=10,
            max_overlap_lines=4,
            max_overlap_fraction=1.0,
        )
        self.assertEqual(views[1].overlap_lines, 4)

    def test_overlap_is_capped_by_fraction(self):
        chunks = (
            TextLogChunkDraft(
                ordinal=0,
                content="\n".join(str(i) for i in range(1, 9)),
                kind=TextLogChunkKind.BLOCK,
                line_start=1,
                line_end=8,
            ),
            TextLogChunkDraft(
                ordinal=1,
                content="\n".join(str(i) for i in range(9, 17)),
                kind=TextLogChunkKind.BLOCK,
                line_start=9,
                line_end=16,
                continuation=True,
            ),
        )
        views = apply_controlled_overlap(
            chunks,
            overlap_lines=4,
            max_overlap_lines=4,
            max_overlap_fraction=0.25,
        )
        self.assertEqual(views[1].overlap_lines, 2)

    def test_small_tail_gets_at_most_one_context_line(self):
        chunks = (
            TextLogChunkDraft(
                ordinal=0,
                content="one\ntwo\nthree",
                kind=TextLogChunkKind.BLOCK,
                line_start=1,
                line_end=3,
            ),
            TextLogChunkDraft(
                ordinal=1,
                content="four",
                kind=TextLogChunkKind.BLOCK,
                line_start=4,
                line_end=4,
                continuation=True,
            ),
        )
        views = apply_controlled_overlap(chunks, overlap_lines=4)
        self.assertEqual(views[1].overlap_lines, 1)
        self.assertEqual(views[1].content, "three\nfour")

    def test_semantic_boundary_does_not_overlap(self):
        chunks = chunk_text_log(
            "one\ntwo\nthree\nERROR failed\ntrace line",
            max_lines=3,
        )
        views = apply_controlled_overlap(chunks)

        self.assertEqual(len(views), 2)
        self.assertEqual(chunks[1].kind, TextLogChunkKind.ERROR)
        self.assertFalse(chunks[1].continuation)
        self.assertFalse(views[1].overlap_applied)

    def test_marker_or_kind_mismatch_blocks_overlap(self):
        previous = TextLogChunkDraft(
            ordinal=0,
            content="execution_id=exec_1\nline",
            kind=TextLogChunkKind.EXECUTION,
            line_start=1,
            line_end=2,
            marker="exec_1",
        )
        current = TextLogChunkDraft(
            ordinal=1,
            content="continued",
            kind=TextLogChunkKind.EXECUTION,
            line_start=3,
            line_end=3,
            continuation=True,
            marker="exec_2",
        )
        views = apply_controlled_overlap((previous, current))
        self.assertFalse(views[1].overlap_applied)

    def test_non_contiguous_ranges_do_not_overlap(self):
        chunks = (
            TextLogChunkDraft(
                ordinal=0,
                content="one",
                kind=TextLogChunkKind.BLOCK,
                line_start=1,
                line_end=1,
            ),
            TextLogChunkDraft(
                ordinal=1,
                content="three",
                kind=TextLogChunkKind.BLOCK,
                line_start=3,
                line_end=3,
                continuation=True,
            ),
        )
        views = apply_controlled_overlap(chunks)
        self.assertFalse(views[1].overlap_applied)

    def test_markdown_does_not_overlap_by_default(self):
        chunks = chunk_markdown(
            "# A\n\nFirst paragraph.\n\nSecond paragraph."
        )
        views = apply_controlled_overlap(chunks)

        self.assertEqual(len(views), 2)
        self.assertFalse(any(view.overlap_applied for view in views))
        self.assertEqual(
            [view.content for view in views],
            [chunk.content for chunk in chunks],
        )

    def test_overlap_zero_disables_duplication(self):
        chunks = chunk_text_log(
            "\n".join(str(i) for i in range(1, 7)),
            max_lines=3,
        )
        views = apply_controlled_overlap(
            chunks,
            overlap_lines=0,
        )
        self.assertFalse(any(view.overlap_applied for view in views))

    def test_source_chunks_are_not_mutated(self):
        chunks = chunk_text_log(
            "\n".join(str(i) for i in range(1, 7)),
            max_lines=3,
        )
        before = tuple(chunks)
        apply_controlled_overlap(chunks)
        self.assertEqual(chunks, before)

    def test_output_is_deterministic(self):
        chunks = chunk_text_log(
            "\n".join(str(i) for i in range(1, 17)),
            max_lines=8,
        )
        self.assertEqual(
            apply_controlled_overlap(chunks),
            apply_controlled_overlap(chunks),
        )

    def test_invalid_policy_values_are_rejected(self):
        chunks = chunk_text_log("one")
        bad_calls = (
            {"overlap_lines": -1},
            {"max_overlap_lines": 0},
            {"max_overlap_fraction": 0},
            {"max_overlap_fraction": 1.1},
            {"max_overlap_fraction": float("nan")},
        )
        for kwargs in bad_calls:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    apply_controlled_overlap(chunks, **kwargs)


if __name__ == "__main__":
    unittest.main()
