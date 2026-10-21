import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.runtime.index_request import RagIndexPlan, RagIndexScope, RagIndexCandidate
from rag.runtime.production_index import build_staged_index


class P1IsolatedStagingBoundaryTests(unittest.TestCase):
    def test_explicit_staging_refuses_production_and_source_roots(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            project=base/"repository"
            project.mkdir()
            state=base/"CodeBridge"/"rag"
            state.mkdir(parents=True)
            plan=RagIndexPlan("codebridge",str(project),RagIndexScope.CODE,
                (RagIndexCandidate("approved.py",False,True),),0,0)
            with patch("rag.runtime.status.resolve_rag_sqlite_path",return_value=state/"rag_index.sqlite3"):
                for denied in (state,state/"staging",project,base):
                    if denied.name=="staging":
                        denied.mkdir()
                    with self.subTest(denied=str(denied)):
                        with self.assertRaises(ValueError):
                            build_staged_index(plan,isolated_staging_parent=denied)
                self.assertFalse((state/"rag_index.sqlite3").exists())
                self.assertFalse((state/"qdrant").exists())

    def test_missing_isolated_parent_does_not_create_it(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            repo=root/"repository"
            repo.mkdir()
            state=root/"CodeBridge"/"rag"
            state.mkdir(parents=True)
            missing=root/"isolated-does-not-exist"
            plan=RagIndexPlan("codebridge",str(repo),RagIndexScope.CODE,
                (RagIndexCandidate("approved.py",False,True),),0,0)
            with patch("rag.runtime.status.resolve_rag_sqlite_path",return_value=state/"rag_index.sqlite3"):
                with self.assertRaises(FileNotFoundError):
                    build_staged_index(plan,isolated_staging_parent=missing)
            self.assertFalse(missing.exists())
