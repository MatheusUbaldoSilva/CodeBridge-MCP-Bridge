"""Isolated bounded indexing test without models or production writes"""

import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.index_request import RagIndexCandidate, RagIndexPlan, RagIndexScope
from rag.runtime.production_index import _drafts, build_staged_index
from rag.chunking.bounded import CODE_INDEX_MAX_CHARS, TEXT_INDEX_MAX_CHARS


class BoundedStagingTests(TestCase):
    def test_staging_sqlite_contains_all_bounded_chunks(self):
        with TemporaryDirectory() as location:
            root = Path(location) / "sources"
            root.mkdir()
            (root / "large.js").write_text(
                'const payload = "' + "x" * 7000 + '";',
                encoding="utf-8",
            )
            (root / "notes.md").write_text(
                "# Notes\n" + ("description line\n" * 400),
                encoding="utf-8",
            )
            plan = RagIndexPlan(
                project_id="codebrige-mcp-rag",
                project_root=str(root),
                scope=RagIndexScope.BOTH,
                candidates=(
                    RagIndexCandidate(
                        path="large.js", text_eligible=False, code_eligible=True
                    ),
                    RagIndexCandidate(
                        path="notes.md", text_eligible=True, code_eligible=False
                    ),
                ),
                denied_count=0,
                unsupported_count=0,
            )
            state = Path(location) / "isolated-production"
            with (
                patch(
                    "rag.runtime.production_index.resolve_rag_sqlite_path",
                    return_value=state / "rag_index.sqlite3",
                ),
                patch(
                    "rag.runtime.status.resolve_rag_manifest_path",
                    return_value=state / "rag-index-manifest.json",
                ),
                patch("rag.runtime.production_index._write_vectors") as vectors,
            ):
                response = build_staged_index(plan)
            self.assertEqual(response["state"], "STAGED_NOT_PUBLISHED")
            self.assertFalse((state / "rag_index.sqlite3").exists())
            self.assertFalse((state / "qdrant").exists())
            vectors.assert_called_once()

            database = Path(response["staging_path"]) / "rag_index.sqlite3"
            with closing(sqlite3.connect(database)) as connection:
                for name, is_code, maximum in (
                    ("large.js", True, CODE_INDEX_MAX_CHARS),
                    ("notes.md", False, TEXT_INDEX_MAX_CHARS),
                ):
                    found = connection.execute(
                        "SELECT content, line_start, line_end FROM rag_chunks "
                        "WHERE project_id=? AND path=? ORDER BY ordinal",
                        ("codebrige-mcp-rag", name),
                    ).fetchall()
                    source = (root / name).read_text(encoding="utf-8")
                    original = _drafts(name, source, is_code)
                    self.assertEqual(
                        [row[0] for row in found],
                        [chunk.content for chunk in original],
                    )
                    self.assertTrue(found)
                    self.assertTrue(all(len(row[0]) <= maximum for row in found))
                    self.assertTrue(all(1 <= row[1] <= row[2] for row in found))


if __name__ == "__main__":
    import unittest
    unittest.main()
