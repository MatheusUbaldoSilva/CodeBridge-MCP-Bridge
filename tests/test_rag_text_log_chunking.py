import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.text_log import (
    TextLogChunkKind,
    chunk_text_log,
)


CORPUS = """boot one
boot two

=== AUTH ===
ready
execution_id=exec_001
started
ERROR command failed
detail
2026-10-07T00:00:01Z INFO recovered
ok
[EXECUTION] exec_002
running
EVENT: sync-complete
finished
"""


class RagTextLogChunkingTests(unittest.TestCase):
    def test_section_execution_error_event_and_generic_boundaries(self):
        chunks = chunk_text_log(CORPUS)

        self.assertEqual(len(chunks), 7)
        self.assertEqual(
            [chunk.kind for chunk in chunks],
            [
                TextLogChunkKind.BLOCK,
                TextLogChunkKind.SECTION,
                TextLogChunkKind.EXECUTION,
                TextLogChunkKind.ERROR,
                TextLogChunkKind.EVENT,
                TextLogChunkKind.EXECUTION,
                TextLogChunkKind.EVENT,
            ],
        )

        self.assertEqual(chunks[0].content, "boot one\nboot two")
        self.assertEqual(chunks[1].marker, "AUTH")
        self.assertEqual(chunks[2].marker, "exec_001")
        self.assertEqual(chunks[3].marker, "ERROR")
        self.assertEqual(chunks[4].marker, "INFO recovered")
        self.assertEqual(chunks[5].marker, "exec_002")
        self.assertEqual(chunks[6].marker, "sync-complete")

    def test_line_ranges_are_deterministic(self):
        chunks = chunk_text_log(CORPUS)
        self.assertEqual(
            [(chunk.line_start, chunk.line_end) for chunk in chunks],
            [
                (1, 2),
                (4, 5),
                (6, 7),
                (8, 9),
                (10, 11),
                (12, 13),
                (14, 15),
            ],
        )

    def test_controlled_limit_splits_without_overlap(self):
        chunks = chunk_text_log(
            "one\ntwo\nthree\nfour\nfive\nsix\nseven",
            max_lines=3,
        )

        self.assertEqual(
            [chunk.content for chunk in chunks],
            [
                "one\ntwo\nthree",
                "four\nfive\nsix",
                "seven",
            ],
        )
        self.assertEqual(
            [chunk.continuation for chunk in chunks],
            [False, True, True],
        )
        self.assertEqual(
            [(chunk.line_start, chunk.line_end) for chunk in chunks],
            [(1, 3), (4, 6), (7, 7)],
        )

    def test_semantic_marker_resets_continuation(self):
        chunks = chunk_text_log(
            "a\nb\nc\nexecution_id=exec_next\nrunning",
            max_lines=3,
        )

        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].kind is TextLogChunkKind.BLOCK)
        self.assertEqual(chunks[1].kind, TextLogChunkKind.EXECUTION)
        self.assertFalse(chunks[1].continuation)
        self.assertEqual(chunks[1].marker, "exec_next")

    def test_bracketed_section_is_recognized(self):
        chunks = chunk_text_log("[SECTION] Network\nlink ready")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].kind, TextLogChunkKind.SECTION)
        self.assertEqual(chunks[0].marker, "Network")

    def test_timestamp_without_timezone_is_event(self):
        chunks = chunk_text_log("2026-10-07 00:14:33 INFO ready\nnext")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].kind, TextLogChunkKind.EVENT)
        self.assertEqual(chunks[0].marker, "INFO ready")

    def test_bracketed_timestamp_error_prefers_error(self):
        chunks = chunk_text_log(
            "[2026-10-07T00:14:33Z] ERROR transport failed\ndetail"
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].kind, TextLogChunkKind.ERROR)
        self.assertEqual(chunks[0].marker, "ERROR")

    def test_blank_edges_are_trimmed_but_internal_lines_preserved(self):
        chunks = chunk_text_log("\n\none\n\ntwo\n\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, "one\n\ntwo")
        self.assertEqual((chunks[0].line_start, chunks[0].line_end), (3, 5))

    def test_output_is_deterministic(self):
        self.assertEqual(
            chunk_text_log(CORPUS, max_lines=4),
            chunk_text_log(CORPUS, max_lines=4),
        )

    def test_empty_input_returns_no_chunks(self):
        self.assertEqual(chunk_text_log("  \n\n"), ())

    def test_invalid_text_is_rejected(self):
        with self.assertRaises(ValueError):
            chunk_text_log(None)

    def test_invalid_max_lines_is_rejected(self):
        for value in (0, -1, True, 1.5, "10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    chunk_text_log("line", max_lines=value)


if __name__ == "__main__":
    unittest.main()
