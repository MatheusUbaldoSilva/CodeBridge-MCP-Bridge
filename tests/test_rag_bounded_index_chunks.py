"""Regression checks for bounded RAG chunks used by staging index"""

import unittest
from dataclasses import replace

from rag.chunking import chunk_markdown, chunk_text_log, safe_chunk_code
from rag.chunking.bounded import (
    CODE_INDEX_MAX_CHARS,
    TEXT_INDEX_MAX_CHARS,
    bound_index_chunks,
)
from rag.runtime.production_index import _drafts


class BoundedIndexChunksTests(unittest.TestCase):
    def test_single_huge_code_line_has_full_coverage_and_correct_line(self):
        source = "const payload = \"" + "x" * 7000 + "\";"
        drafts = _drafts("src/generated.js", source, True)
        self.assertGreater(len(drafts), 1)
        self.assertEqual("".join(item.content for item in drafts), source)
        self.assertTrue(all(len(item.content) <= CODE_INDEX_MAX_CHARS for item in drafts))
        self.assertTrue(all((item.line_start, item.line_end) == (1, 1) for item in drafts))
        self.assertEqual(
            [item.ordinal for item in drafts],
            list(range(len(drafts))),
        )

    def test_long_python_function_preserves_each_original_structural_chunk(self):
        source = "def example():\n    message = \"" + "x" * 7000 + "\"\n    return message\n"
        original = safe_chunk_code(source, path="src/example.py")
        original_drafts = original.structural_chunks or original.fallback_chunks
        new = _drafts("src/example.py", source, True)
        self.assertEqual(
            "".join(chunk.content for chunk in new),
            "".join(chunk.content for chunk in original_drafts),
        )
        self.assertTrue(all(len(chunk.content) <= CODE_INDEX_MAX_CHARS for chunk in new))
        self.assertTrue(all(1 <= chunk.line_start <= chunk.line_end <= 3 for chunk in new))

    def test_markdown_preserves_semantic_chunks(self):
        source = "# Section\n" + ("long description\n" * 320)
        original = chunk_markdown(source)
        bounded = _drafts("docs/explain.md", source, False)
        self.assertEqual("".join(item.content for item in bounded),
                         "".join(item.content for item in original))
        self.assertTrue(all(len(item.content) <= TEXT_INDEX_MAX_CHARS for item in bounded))

    def test_log_preserves_semantic_chunks(self):
        source = "[ERROR] " + ("trace " * 700) + "\n"
        original = chunk_text_log(source)
        bounded = _drafts("logs/test.log", source, False)
        self.assertEqual("".join(item.content for item in bounded),
                         "".join(item.content for item in original))
        self.assertTrue(all(len(item.content) <= TEXT_INDEX_MAX_CHARS for item in bounded))

    def test_small_chunk_remains_identical(self):
        source = "def short():\n    return 5\n"
        original = safe_chunk_code(source, path="src/short.py")
        originals = original.structural_chunks or original.fallback_chunks
        bounded = _drafts("src/short.py", source, True)
        self.assertEqual([(x.content, x.line_start, x.line_end) for x in bounded],
                         [(x.content, x.line_start, x.line_end) for x in originals])

    def test_fallback_continuation(self):
        source = "not python syntax \xff\n" + ("value = " + "x" * 5000)
        original = safe_chunk_code(source, path="src/file.xyz")
        originals = original.structural_chunks or original.fallback_chunks
        self.assertTrue(originals)
        bounded = bound_index_chunks(originals, max_chars=CODE_INDEX_MAX_CHARS)
        self.assertEqual("".join(x.content for x in bounded),
                         "".join(x.content for x in originals))
        self.assertTrue(any(x.continuation for x in bounded[1:]))

    def test_reject_invalid_size(self):
        source = chunk_text_log("some text")
        for bad in (0, -1, True, 1.5, "100"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    bound_index_chunks(source, max_chars=bad)

    def test_whitespace_only_large_piece_fails_without_losing_data(self):
        source = chunk_text_log("x" + " " * 4000)
        with self.assertRaises(ValueError):
            bound_index_chunks(source, max_chars=12)


if __name__ == "__main__":
    unittest.main()
