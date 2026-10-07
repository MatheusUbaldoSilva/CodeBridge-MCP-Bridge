import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.chunking.markdown import chunk_markdown
from rag.chunking.provenance import (
    attach_source_provenance,
    source_sha256,
)
from rag.chunking.text_log import chunk_text_log
from rag.contracts import SourceType


MARKDOWN = """# Alpha

First paragraph.

Second paragraph.
"""

LOG = """=== RUN ===
execution_id=exec_1
line one
line two
line three
line four
"""


class RagChunkProvenanceTests(unittest.TestCase):
    def test_markdown_chunks_receive_required_provenance(self):
        drafts = chunk_markdown(MARKDOWN)
        chunks = attach_source_provenance(
            drafts,
            source_text=MARKDOWN,
            project_id="codebridge",
            path=r"docs\example.md",
            source_type=SourceType.DOCUMENTATION,
            indexed_at="2026-10-07T00:14:00-03:00",
            document_id="doc-test",
            chunk_ids=("chunk-a", "chunk-b"),
            git_branch="rag-003-text-chunking",
            git_commit="8aec852d0f6f89d1f46b972ea8a6aaed494289d9",
        )

        self.assertEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertEqual(chunk.metadata.project_id, "codebridge")
            self.assertEqual(
                chunk.metadata.source_type,
                SourceType.DOCUMENTATION,
            )
            self.assertEqual(chunk.metadata.path, "docs/example.md")
            self.assertEqual(
                chunk.metadata.sha256,
                hashlib.sha256(MARKDOWN.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(
                chunk.metadata.indexed_at,
                "2026-10-07T00:14:00-03:00",
            )
            self.assertGreaterEqual(chunk.metadata.line_start, 1)
            self.assertGreaterEqual(
                chunk.metadata.line_end,
                chunk.metadata.line_start,
            )

    def test_text_log_chunks_keep_exact_line_ranges(self):
        drafts = chunk_text_log(LOG, max_lines=3)
        ids = tuple(f"chunk-{index}" for index in range(len(drafts)))
        chunks = attach_source_provenance(
            drafts,
            source_text=LOG,
            project_id="codebridge",
            path="auditoria/runtime.log",
            source_type=SourceType.LOG,
            indexed_at="2026-10-07T03:14:00Z",
            document_id="doc-log",
            chunk_ids=ids,
        )

        source_lines = LOG.splitlines()
        for chunk in chunks:
            start = chunk.metadata.line_start
            end = chunk.metadata.line_end
            self.assertEqual(
                chunk.content,
                "\n".join(source_lines[start - 1:end]),
            )

    def test_sha256_is_source_hash_not_chunk_hash(self):
        drafts = chunk_markdown(MARKDOWN)
        chunks = attach_source_provenance(
            drafts,
            source_text=MARKDOWN,
            project_id="codebridge",
            path="docs/example.md",
            source_type=SourceType.DOCUMENTATION,
            indexed_at="2026-10-07T03:14:00Z",
            document_id="doc-test",
            chunk_ids=("a", "b"),
        )
        source_hash = source_sha256(MARKDOWN)
        self.assertEqual({c.metadata.sha256 for c in chunks}, {source_hash})
        self.assertNotEqual(
            source_hash,
            hashlib.sha256(chunks[0].content.encode("utf-8")).hexdigest(),
        )

    def test_tampered_draft_content_is_rejected(self):
        drafts = list(chunk_markdown(MARKDOWN))
        original = drafts[0]
        tampered = type(original)(
            ordinal=original.ordinal,
            content=original.content + " tampered",
            heading_path=original.heading_path,
            heading_level=original.heading_level,
            line_start=original.line_start,
            line_end=original.line_end,
            kind=original.kind,
        )
        drafts[0] = tampered

        with self.assertRaisesRegex(ValueError, "does not match source text"):
            attach_source_provenance(
                drafts,
                source_text=MARKDOWN,
                project_id="codebridge",
                path="docs/example.md",
                source_type=SourceType.DOCUMENTATION,
                indexed_at="2026-10-07T03:14:00Z",
                document_id="doc-test",
                chunk_ids=("a", "b"),
            )

    def test_out_of_range_lines_are_rejected(self):
        drafts = list(chunk_markdown(MARKDOWN))
        original = drafts[0]
        bad = type(original)(
            ordinal=original.ordinal,
            content=original.content,
            heading_path=original.heading_path,
            heading_level=original.heading_level,
            line_start=original.line_start,
            line_end=999,
            kind=original.kind,
        )
        drafts[0] = bad
        with self.assertRaisesRegex(ValueError, "exceeds source text"):
            attach_source_provenance(
                drafts,
                source_text=MARKDOWN,
                project_id="codebridge",
                path="docs/example.md",
                source_type=SourceType.DOCUMENTATION,
                indexed_at="2026-10-07T03:14:00Z",
                document_id="doc-test",
                chunk_ids=("a", "b"),
            )

    def test_relative_path_is_required(self):
        drafts = chunk_markdown("# A")
        for path in ("../secret.md", "/absolute/file.md", r"C:\absolute\file.md"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    attach_source_provenance(
                        drafts,
                        source_text="# A",
                        project_id="codebridge",
                        path=path,
                        source_type=SourceType.DOCUMENTATION,
                        indexed_at="2026-10-07T03:14:00Z",
                        document_id="doc-test",
                        chunk_ids=("a",),
                    )

    def test_indexed_at_requires_iso8601_timezone(self):
        drafts = chunk_markdown("# A")
        for value in ("2026-10-07", "not-a-date", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    attach_source_provenance(
                        drafts,
                        source_text="# A",
                        project_id="codebridge",
                        path="docs/a.md",
                        source_type=SourceType.DOCUMENTATION,
                        indexed_at=value,
                        document_id="doc-test",
                        chunk_ids=("a",),
                    )

    def test_chunk_ids_must_match_count_and_be_unique(self):
        drafts = chunk_markdown(MARKDOWN)
        with self.assertRaisesRegex(ValueError, "length"):
            attach_source_provenance(
                drafts,
                source_text=MARKDOWN,
                project_id="codebridge",
                path="docs/example.md",
                source_type=SourceType.DOCUMENTATION,
                indexed_at="2026-10-07T03:14:00Z",
                document_id="doc-test",
                chunk_ids=("only-one",),
            )

        with self.assertRaisesRegex(ValueError, "unique"):
            attach_source_provenance(
                drafts,
                source_text=MARKDOWN,
                project_id="codebridge",
                path="docs/example.md",
                source_type=SourceType.DOCUMENTATION,
                indexed_at="2026-10-07T03:14:00Z",
                document_id="doc-test",
                chunk_ids=("same", "same"),
            )

    def test_source_type_must_use_contract_enum(self):
        drafts = chunk_markdown("# A")
        with self.assertRaisesRegex(ValueError, "SourceType"):
            attach_source_provenance(
                drafts,
                source_text="# A",
                project_id="codebridge",
                path="docs/a.md",
                source_type="DOCUMENTATION",
                indexed_at="2026-10-07T03:14:00Z",
                document_id="doc-test",
                chunk_ids=("a",),
            )

    def test_no_id_policy_is_invented_here(self):
        drafts = chunk_markdown("# A")
        chunks = attach_source_provenance(
            drafts,
            source_text="# A",
            project_id="codebridge",
            path="docs/a.md",
            source_type=SourceType.DOCUMENTATION,
            indexed_at="2026-10-07T03:14:00Z",
            document_id="caller-doc-id",
            chunk_ids=("caller-chunk-id",),
        )
        self.assertEqual(chunks[0].document_id, "caller-doc-id")
        self.assertEqual(chunks[0].chunk_id, "caller-chunk-id")


if __name__ == "__main__":
    unittest.main()
