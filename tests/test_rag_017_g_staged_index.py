"""RAG-017-G staging index regression, no publication into production."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil
import unittest

from rag.runtime.index_request import RagIndexPlan, RagIndexScope, RagIndexCandidate
from rag.runtime.production_index import build_staged_index

class StagedIndexTests(unittest.TestCase):
    def test_invalid_plan_fails_before_writes(self):
        with self.assertRaises(ValueError):
            build_staged_index(object())

    def test_empty_plan_creates_isolated_staging_only(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            plan=RagIndexPlan(
                project_id="demo",project_root=str(root),
                scope=RagIndexScope.BOTH,candidates=(),
                denied_count=0,unsupported_count=0,
            )
            with patch("rag.runtime.production_index.resolve_rag_sqlite_path",
                       return_value=root/"production"/"rag_index.sqlite3"):
                with patch("rag.runtime.production_index._write_vectors"):
                    result=build_staged_index(plan)
            staged=Path(result["staging_path"])
            try:
                self.assertEqual(result["state"],"STAGED_NOT_PUBLISHED")
                self.assertEqual(result["documents"],0)
                self.assertTrue((staged/"rag_index.sqlite3").is_file())
                self.assertFalse((root/"production"/"rag_index.sqlite3").exists())
            finally:
                shutil.rmtree(staged)
if __name__=="__main__":
    unittest.main()
