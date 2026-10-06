import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.contracts import (
    Chunk,
    Document,
    IndexState,
    ModelState,
    SearchQuery,
    SearchResult,
    SourceMetadata,
    SourceType,
)


class RagContractTests(unittest.TestCase):
    def setUp(self):
        self.meta = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="author_mcp/mcp_server.py",
            symbol="codebridge_exec",
            line_start=100,
            line_end=140,
            git_branch="main",
            git_commit="8730998a15f9f36c2a5cf71112c45453429e08bc",
            sha256="a" * 64,
            indexed_at="2026-10-06T00:00:00Z",
        )

    def test_source_metadata_preserves_provenance(self):
        self.assertEqual(self.meta.project_id, "codebridge")
        self.assertEqual(self.meta.source_type, SourceType.CODE)
        self.assertEqual(self.meta.line_start, 100)
        self.assertEqual(self.meta.line_end, 140)
        self.assertEqual(self.meta.sha256, "a" * 64)

    def test_source_metadata_rejects_invalid_line_range(self):
        with self.assertRaises(ValueError):
            SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                line_start=20,
                line_end=10,
            )

    def test_source_metadata_rejects_invalid_sha256(self):
        with self.assertRaises(ValueError):
            SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                sha256="not-a-sha256",
            )

    def test_document_and_chunk_are_side_effect_free_data_objects(self):
        document = Document(
            document_id="doc-1",
            content="alpha",
            metadata=self.meta,
        )
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id=document.document_id,
            content="alpha",
            metadata=self.meta,
            ordinal=0,
        )
        self.assertEqual(chunk.document_id, "doc-1")
        self.assertEqual(chunk.metadata.path, "author_mcp/mcp_server.py")

    def test_chunk_rejects_empty_content(self):
        with self.assertRaises(ValueError):
            Chunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="",
                metadata=self.meta,
            )

    def test_search_query_validates_scope_and_top_k(self):
        query = SearchQuery(
            query="onde controla cancelamento",
            project_id="codebridge",
            source_types=(SourceType.CODE, SourceType.DOCUMENTATION),
            top_k=5,
            path_filter="author_mcp/",
            branch="main",
        )
        self.assertEqual(query.top_k, 5)
        self.assertEqual(len(query.source_types), 2)

        with self.assertRaises(ValueError):
            SearchQuery(
                query="consulta",
                project_id="codebridge",
                top_k=0,
            )

    def test_search_result_validates_rank_and_score(self):
        result = SearchResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="resultado",
            metadata=self.meta,
            score=0.91,
            rank=1,
            retrieval_modes=("lexical", "vector"),
            stale=False,
        )
        self.assertEqual(result.rank, 1)
        self.assertFalse(result.stale)

        with self.assertRaises(ValueError):
            SearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="resultado",
                metadata=self.meta,
                score=float("nan"),
                rank=1,
            )

        with self.assertRaises(ValueError):
            SearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="resultado",
                metadata=self.meta,
                score=0.5,
                rank=0,
            )

    def test_contracts_are_immutable(self):
        query = SearchQuery(
            query="status",
            project_id="codebridge",
        )
        with self.assertRaises(FrozenInstanceError):
            query.top_k = 20

    def test_state_contracts_are_explicit(self):
        self.assertEqual(ModelState.UNLOADED.value, "UNLOADED")
        self.assertEqual(ModelState.READY.value, "READY")
        self.assertEqual(IndexState.UNAVAILABLE.value, "UNAVAILABLE")
        self.assertEqual(IndexState.STALE.value, "STALE")


if __name__ == "__main__":
    unittest.main()
