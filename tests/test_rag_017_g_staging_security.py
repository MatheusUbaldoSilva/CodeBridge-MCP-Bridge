"""RAG-017-G fail-closed staging and Git provenance."""
import shutil
import sqlite3
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from rag.runtime.index_request import (
    RagIndexCandidate, RagIndexPlan, RagIndexScope, plan_rag_index,
)
from rag.runtime.production_index import build_staged_index

class StagingSafetyTests(unittest.TestCase):
    def test_sensitive_path_cannot_bypass_planning(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/".env").write_text("SECRET=example",encoding="utf-8")
            plan=RagIndexPlan(
                project_id="demo",project_root=str(root),scope=RagIndexScope.TEXT,
                candidates=(RagIndexCandidate(path=".env",text_eligible=True,code_eligible=False),),
                denied_count=0,unsupported_count=0,
            )
            with patch("rag.runtime.production_index.resolve_rag_sqlite_path",return_value=root/"state"/"index.db"):
                with self.assertRaises(ValueError):
                    build_staged_index(plan)
            self.assertFalse(list((root/"state"/"staging").glob("build-*")))
    def test_failed_vector_build_cleans_staging(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/"readme.md").write_text("# Simple test\nhello world",encoding="utf-8")
            plan=plan_rag_index("demo",root,scope=RagIndexScope.TEXT,paths=("readme.md",))
            with patch("rag.runtime.production_index.resolve_rag_sqlite_path",return_value=root/"state"/"index.db"):
                with patch("rag.runtime.production_index._write_vectors",side_effect=RuntimeError("simulated model failure")):
                    with self.assertRaisesRegex(RuntimeError,"simulated model failure"):
                        build_staged_index(plan)
            self.assertFalse(list((root/"state"/"staging").glob("build-*")))
    @unittest.skipUnless(shutil.which("git"),"Git unavailable")
    def test_git_branch_and_commit_are_stored(self):
        with TemporaryDirectory() as td:
            root=Path(td)/"project"
            root.mkdir()
            (root/"notes.md").write_text("# Notes\nGit provenance available",encoding="utf-8")
            subprocess.run(["git","init","-q",str(root)],check=True)
            subprocess.run(["git","-C",str(root),"add","notes.md"],check=True)
            subprocess.run(["git","-C",str(root),"-c","user.name=Test","-c","user.email=test@example.invalid","commit","-qm","initial"],check=True)
            plan=plan_rag_index("demo",root,scope=RagIndexScope.TEXT,paths=("notes.md",))
            with patch("rag.runtime.production_index.resolve_rag_sqlite_path",return_value=Path(td)/"state"/"index.db"):
                with patch("rag.runtime.production_index._write_vectors"):
                    result=build_staged_index(plan)
            stage=Path(result["staging_path"])
            try:
                connection=sqlite3.connect(str(stage/"rag_index.sqlite3"))
                try:
                    branch,commit=connection.execute("SELECT git_branch,git_commit FROM rag_chunks LIMIT 1").fetchone()
                finally:
                    connection.close()
                self.assertTrue(branch)
                self.assertEqual(len(commit),40)
            finally:
                shutil.rmtree(stage)
