import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.contracts import SourceMetadata, SourceType
from rag.index.sqlite_schema import connect_rag_index
from rag.runtime.context_service import (
    RagContextInvalidScopeError,
    get_context,
)
from rag.runtime.index_request import plan_rag_index
from rag.sources.exclusion_policy import DenyReason, classify_denied_path
from rag.sources.git_provenance import capture_git_file_provenance
from rag.sources.git_worktree import capture_git_path_state
from rag.sources.staleness import evaluate_source_staleness


def run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class Rag015PathTraversalSecurityTests(unittest.TestCase):
    def make_project(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        root = base / "project"
        root.mkdir()
        (root / "inside.py").write_text(
            "print('inside')\n",
            encoding="utf-8",
        )
        outside = base / "outside.py"
        outside.write_text(
            "print('outside')\n",
            encoding="utf-8",
        )
        return root, outside

    def make_git_repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        repo = base / "repo"
        repo.mkdir()
        run_git(repo, "init", "-b", "main")
        run_git(repo, "config", "user.email", "rag@example.test")
        run_git(repo, "config", "user.name", "RAG Test")
        tracked = repo / "inside.txt"
        tracked.write_text("inside\n", encoding="utf-8")
        run_git(repo, "add", "inside.txt")
        run_git(repo, "commit", "-m", "initial")
        outside = base / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        return repo, outside

    def test_path_denylist_handles_posix_and_windows_traversal(self):
        cases = (
            "../outside.py",
            "docs/../../outside.md",
            r"..\outside.py",
            r"docs\..\..\outside.md",
        )
        for path in cases:
            with self.subTest(path=path):
                self.assertEqual(
                    classify_denied_path(path),
                    DenyReason.PATH_TRAVERSAL,
                )

    def test_index_plan_rejects_posix_windows_and_absolute_escape(self):
        root, outside = self.make_project()
        escapes = (
            "../outside.py",
            r"..\outside.py",
            str(outside.resolve()),
        )

        for path in escapes:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    plan_rag_index(
                        "codebridge",
                        root,
                        paths=(path,),
                    )

    def test_index_plan_accepts_normalized_path_that_stays_inside_root(self):
        root, _ = self.make_project()

        plan = plan_rag_index(
            "codebridge",
            root,
            paths=("sub/../inside.py",),
        )

        self.assertEqual(
            [item.path for item in plan.candidates],
            ["inside.py"],
        )

    def test_staleness_rejects_metadata_path_outside_root(self):
        root, outside = self.make_project()
        sha = hashlib.sha256(
            outside.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="../outside.py",
            sha256=sha,
        )

        with self.assertRaises(ValueError):
            evaluate_source_staleness(root, metadata)

    def test_get_context_rejects_traversal_path_even_if_index_contains_it(self):
        root, _ = self.make_project()
        db = root / "rag.sqlite3"
        connection = connect_rag_index(db)
        try:
            connection.execute(
                """
                INSERT INTO rag_documents (
                    document_id,
                    project_id,
                    source_type,
                    content,
                    path
                ) VALUES (
                    'doc-escape',
                    'codebridge',
                    'DOCUMENTATION',
                    'malicious',
                    '../outside.md'
                )
                """
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
                    path
                ) VALUES (
                    'chunk-escape',
                    'doc-escape',
                    'codebridge',
                    0,
                    'malicious',
                    'DOCUMENTATION',
                    '../outside.md'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RagContextInvalidScopeError):
            get_context(
                project_id="codebridge",
                chunk_ids=("chunk-escape",),
                sqlite_path=db,
            )

    def test_git_provenance_rejects_traversal_before_git_path_lookup(self):
        repo, outside = self.make_git_repo()

        for path in ("../outside.txt", str(outside.resolve())):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    capture_git_file_provenance(repo, path)

    def test_git_worktree_rejects_traversal_before_status_lookup(self):
        repo, outside = self.make_git_repo()

        for path in ("../outside.txt", str(outside.resolve())):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    capture_git_path_state(repo, path)


if __name__ == "__main__":
    unittest.main()
