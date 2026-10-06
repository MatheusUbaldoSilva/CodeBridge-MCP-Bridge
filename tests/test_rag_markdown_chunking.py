import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.markdown import (
    MarkdownChunkKind,
    chunk_markdown,
)


CORPUS = """Preamble one.

Preamble two.

# Alpha

Intro paragraph.

- one
- two

## Beta

```python
# not a heading

print("x")
```

Tail text.

Gamma
=====

Body.
"""


class RagMarkdownChunkingTests(unittest.TestCase):
    def test_heading_subsection_and_logical_blocks(self):
        chunks = chunk_markdown(CORPUS)

        self.assertEqual(len(chunks), 7)

        self.assertEqual(chunks[0].kind, MarkdownChunkKind.PREAMBLE)
        self.assertEqual(chunks[0].heading_path, ())
        self.assertEqual(chunks[0].content, "Preamble one.")

        self.assertEqual(chunks[2].heading_path, ("Alpha",))
        self.assertEqual(chunks[2].heading_level, 1)
        self.assertEqual(
            chunks[2].content,
            "# Alpha\n\nIntro paragraph.",
        )

        self.assertEqual(chunks[3].heading_path, ("Alpha",))
        self.assertEqual(chunks[3].content, "- one\n- two")

        self.assertEqual(
            chunks[4].heading_path,
            ("Alpha", "Beta"),
        )
        self.assertEqual(chunks[4].heading_level, 2)

        self.assertEqual(chunks[6].heading_path, ("Gamma",))
        self.assertEqual(chunks[6].heading_level, 1)

    def test_fenced_code_does_not_create_false_heading(self):
        chunks = chunk_markdown(CORPUS)
        beta = chunks[4]

        self.assertIn("# not a heading", beta.content)
        self.assertEqual(
            [chunk.heading_path for chunk in chunks].count(
                ("Alpha", "Beta")
            ),
            2,
        )

    def test_blank_lines_inside_fenced_code_do_not_split_block(self):
        chunks = chunk_markdown(CORPUS)
        beta = chunks[4]

        self.assertIn(
            '```python\n# not a heading\n\nprint("x")\n```',
            beta.content,
        )

    def test_setext_heading_is_supported(self):
        chunks = chunk_markdown(
            "Title\n=====\n\nParagraph."
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading_path, ("Title",))
        self.assertEqual(chunks[0].heading_level, 1)
        self.assertEqual(chunks[0].line_start, 1)
        self.assertEqual(chunks[0].line_end, 4)

    def test_atx_closing_hashes_do_not_damage_csharp_title(self):
        chunks = chunk_markdown(
            "# C#\n\nLanguage notes.\n\n## Child ###\n\nBody."
        )

        self.assertEqual(chunks[0].heading_path, ("C#",))
        self.assertEqual(
            chunks[1].heading_path,
            ("C#", "Child"),
        )

    def test_plain_markdown_falls_back_to_logical_blocks(self):
        chunks = chunk_markdown(
            "First paragraph.\n\nSecond paragraph.\ncontinued."
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].kind, MarkdownChunkKind.PREAMBLE)
        self.assertEqual(chunks[0].content, "First paragraph.")
        self.assertEqual(
            chunks[1].content,
            "Second paragraph.\ncontinued.",
        )

    def test_heading_without_body_is_preserved(self):
        chunks = chunk_markdown("# Empty")

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, "# Empty")
        self.assertEqual(chunks[0].heading_path, ("Empty",))

    def test_line_ranges_are_deterministic_and_non_overlapping(self):
        chunks = chunk_markdown(CORPUS)
        ranges = [
            (chunk.line_start, chunk.line_end)
            for chunk in chunks
        ]

        self.assertEqual(
            ranges,
            [
                (1, 1),
                (3, 3),
                (5, 7),
                (9, 10),
                (12, 18),
                (20, 20),
                (22, 25),
            ],
        )

        for previous, current in zip(chunks, chunks[1:]):
            self.assertLess(previous.line_end, current.line_start)

    def test_output_is_deterministic(self):
        self.assertEqual(
            chunk_markdown(CORPUS),
            chunk_markdown(CORPUS),
        )

    def test_no_overlap_is_applied_in_rag_003_a(self):
        chunks = chunk_markdown(
            "# A\n\nOne.\n\nTwo.\n\nThree."
        )

        contents = [chunk.content for chunk in chunks]
        self.assertEqual(
            contents,
            ["# A\n\nOne.", "Two.", "Three."],
        )

    def test_empty_markdown_returns_no_chunks(self):
        self.assertEqual(chunk_markdown("  \n\n"), ())

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(ValueError):
            chunk_markdown(None)


if __name__ == "__main__":
    unittest.main()
