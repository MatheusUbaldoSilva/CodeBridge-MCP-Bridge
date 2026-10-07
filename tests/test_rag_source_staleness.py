import hashlib
import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.sources.staleness import (
    StalenessStatus,
    evaluate_source_staleness,
    mark_search_result_staleness,
)


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RagSourceStalenessTests(unittest.TestCase):
    def test_unchanged_file_is_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "src.txt"
            content = "alpha\nbeta\n"
            path.write_text(content, encoding="utf-8")
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src.txt",
                sha256=sha256_text(content),
            )

            evaluation = evaluate_source_staleness(root, metadata)

            self.assertEqual(evaluation.status, StalenessStatus.FRESH)
            self.assertFalse(evaluation.stale)
            self.assertEqual(evaluation.reason, "SHA_MATCH")
            self.assertEqual(evaluation.current_sha256, metadata.sha256)

    def test_file_changed_after_indexing_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "src.txt"
            indexed = "alpha\nbeta\n"
            path.write_text(indexed, encoding="utf-8")
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src.txt",
                sha256=sha256_text(indexed),
            )

            path.write_text("alpha\nbeta changed\n", encoding="utf-8")
            evaluation = evaluate_source_staleness(root, metadata)

            self.assertEqual(evaluation.status, StalenessStatus.STALE)
            self.assertTrue(evaluation.stale)
            self.assertEqual(evaluation.reason, "SHA_MISMATCH")
            self.assertNotEqual(
                evaluation.current_sha256,
                evaluation.indexed_sha256,
            )

    def test_deleted_file_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="deleted.txt",
                sha256=sha256_text("old"),
            )

            evaluation = evaluate_source_staleness(root, metadata)

            self.assertEqual(evaluation.status, StalenessStatus.STALE)
            self.assertEqual(evaluation.reason, "FILE_MISSING")

    def test_missing_path_or_sha_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            without_path = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                sha256=sha256_text("x"),
            )
            without_sha = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="x.txt",
            )

            a = evaluate_source_staleness(root, without_path)
            b = evaluate_source_staleness(root, without_sha)

            self.assertEqual(a.status, StalenessStatus.UNKNOWN)
            self.assertEqual(a.reason, "PATH_UNAVAILABLE")
            self.assertEqual(b.status, StalenessStatus.UNKNOWN)
            self.assertEqual(b.reason, "INDEXED_SHA_UNAVAILABLE")

    def test_mark_search_result_sets_stale_flag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "src.txt"
            path.write_text("new", encoding="utf-8")
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src.txt",
                sha256=sha256_text("old"),
            )
            result = SearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="old",
                metadata=metadata,
                score=1.0,
                rank=1,
                retrieval_modes=("TEST",),
                stale=False,
            )

            evaluation = evaluate_source_staleness(root, metadata)
            marked = mark_search_result_staleness(result, evaluation)

            self.assertTrue(marked.stale)
            self.assertFalse(result.stale)

    def test_fresh_evaluation_clears_previous_stale_flag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = "same"
            (root / "src.txt").write_text(content, encoding="utf-8")
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src.txt",
                sha256=sha256_text(content),
            )
            result = SearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content=content,
                metadata=metadata,
                score=1.0,
                rank=1,
                stale=True,
            )

            evaluation = evaluate_source_staleness(root, metadata)
            marked = mark_search_result_staleness(result, evaluation)

            self.assertFalse(marked.stale)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            metadata = SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="../outside.txt",
                sha256=sha256_text("x"),
            )

            with self.assertRaises(ValueError):
                evaluate_source_staleness(root, metadata)


if __name__ == "__main__":
    unittest.main()
