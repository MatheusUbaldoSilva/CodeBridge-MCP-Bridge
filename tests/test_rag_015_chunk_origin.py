import tempfile
import unittest
from pathlib import Path

from rag.chunking.markdown import chunk_markdown
from rag.chunking.provenance import (
    ChunkOriginRecord,
    attach_source_provenance,
    require_chunk_origin,
    source_sha256,
)
from rag.contracts import Chunk, SearchQuery, SourceMetadata, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import search_lexical_ranked
from rag.index.sqlite_schema import connect_rag_index


INDEXED_AT = "2026-10-08T19:00:00-03:00"


class Rag015ChunkOriginTests(unittest.TestCase):
    def make_originated_chunk(self):
        source = "# Security\n\nEvery chunk keeps its source origin.\n"
        drafts = chunk_markdown(source)
        chunks = attach_source_provenance(
            drafts,
            source_text=source,
            project_id="codebridge",
            path="docs/security.md",
            source_type=SourceType.DOCUMENTATION,
            indexed_at=INDEXED_AT,
            document_id="doc-security",
            chunk_ids=[
                f"chunk-security-{index}"
                for index in range(len(drafts))
            ],
            source_id="source-security",
        )
        self.assertTrue(chunks)
        return source, chunks[0]

    def test_official_provenance_produces_complete_origin_record(self):
        source, chunk = self.make_originated_chunk()

        origin = require_chunk_origin(chunk)

        self.assertIsInstance(origin, ChunkOriginRecord)
        self.assertEqual(origin.chunk_id, chunk.chunk_id)
        self.assertEqual(origin.document_id, "doc-security")
        self.assertEqual(origin.project_id, "codebridge")
        self.assertEqual(origin.source_type, SourceType.DOCUMENTATION)
        self.assertEqual(origin.path, "docs/security.md")
        self.assertGreaterEqual(origin.line_start, 1)
        self.assertGreaterEqual(origin.line_end, origin.line_start)
        self.assertEqual(origin.sha256, source_sha256(source))
        self.assertEqual(origin.indexed_at, INDEXED_AT)
        self.assertEqual(origin.source_id, "source-security")

    def test_origin_record_payload_contains_no_chunk_content_copy(self):
        _, chunk = self.make_originated_chunk()

        payload = require_chunk_origin(chunk).to_dict()

        self.assertNotIn("content", payload)
        self.assertEqual(payload["path"], "docs/security.md")
        self.assertEqual(payload["source_type"], "DOCUMENTATION")
        self.assertEqual(payload["source_id"], "source-security")

    def test_missing_path_is_rejected(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                line_start=1,
                line_end=1,
                sha256="a" * 64,
                indexed_at=INDEXED_AT,
            ),
        )
        with self.assertRaisesRegex(ValueError, "requires path"):
            require_chunk_origin(chunk)

    def test_missing_line_range_is_rejected(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                path="docs/x.md",
                sha256="a" * 64,
                indexed_at=INDEXED_AT,
            ),
        )
        with self.assertRaisesRegex(ValueError, "line_start and line_end"):
            require_chunk_origin(chunk)

    def test_missing_sha_is_rejected(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                path="docs/x.md",
                line_start=1,
                line_end=1,
                indexed_at=INDEXED_AT,
            ),
        )
        with self.assertRaisesRegex(ValueError, "source sha256"):
            require_chunk_origin(chunk)

    def test_missing_indexed_at_is_rejected(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                path="docs/x.md",
                line_start=1,
                line_end=1,
                sha256="a" * 64,
            ),
        )
        with self.assertRaisesRegex(ValueError, "indexed_at"):
            require_chunk_origin(chunk)

    def test_windows_separator_is_normalized_in_origin_record(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                path=r"docs\security.md",
                line_start=1,
                line_end=1,
                sha256="a" * 64,
                indexed_at=INDEXED_AT,
            ),
        )

        origin = require_chunk_origin(chunk)

        self.assertEqual(origin.path, "docs/security.md")

    def test_traversal_path_is_rejected(self):
        chunk = Chunk(
            chunk_id="c",
            document_id="d",
            content="x",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.DOCUMENTATION,
                path="../outside.md",
                line_start=1,
                line_end=1,
                sha256="a" * 64,
                indexed_at=INDEXED_AT,
            ),
        )
        with self.assertRaises(ValueError):
            require_chunk_origin(chunk)

    def test_origin_survives_sqlite_fts_round_trip(self):
        source, chunk = self.make_originated_chunk()
        origin = require_chunk_origin(chunk)

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "rag.sqlite3"
            connection = connect_rag_index(db)
            try:
                connection.execute(
                    """
                    INSERT INTO rag_documents (
                        document_id,
                        project_id,
                        source_type,
                        content,
                        path,
                        sha256,
                        indexed_at,
                        source_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.document_id,
                        origin.project_id,
                        origin.source_type.value,
                        source,
                        origin.path,
                        origin.sha256,
                        origin.indexed_at,
                        origin.source_id,
                    ),
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
                        line_start,
                        line_end,
                        sha256,
                        indexed_at,
                        source_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        origin.project_id,
                        chunk.ordinal,
                        chunk.content,
                        origin.source_type.value,
                        origin.path,
                        origin.line_start,
                        origin.line_end,
                        origin.sha256,
                        origin.indexed_at,
                        origin.source_id,
                    ),
                )
                connection.commit()
                initialize_fts5(connection)

                results = search_lexical_ranked(
                    connection,
                    SearchQuery(
                        query="Security",
                        project_id="codebridge",
                        top_k=5,
                    ),
                )
            finally:
                connection.close()

        self.assertTrue(results)
        metadata = results[0].metadata
        self.assertEqual(metadata.path, origin.path)
        self.assertEqual(metadata.line_start, origin.line_start)
        self.assertEqual(metadata.line_end, origin.line_end)
        self.assertEqual(metadata.sha256, origin.sha256)
        self.assertEqual(metadata.indexed_at, origin.indexed_at)
        self.assertEqual(metadata.source_id, origin.source_id)


if __name__ == "__main__":
    unittest.main()
