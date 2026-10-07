import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.sources.git_provenance import (
    GitFileProvenance,
    GitProvenanceError,
    attach_git_provenance_to_chunk,
    attach_git_provenance_to_metadata,
    capture_git_file_provenance,
)


def run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class RagGitFileProvenanceTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "repo"
        repo.mkdir()

        run_git(repo, "init", "-b", "rag-test")
        run_git(repo, "config", "user.email", "rag@example.test")
        run_git(repo, "config", "user.name", "RAG Test")

        src = repo / "src"
        src.mkdir()
        path = src / "main.py"
        path.write_text(
            "alpha = 1\n"
            "beta = 2\n"
            "gamma = 3\n"
            "delta = 4\n",
            encoding="utf-8",
        )
        run_git(repo, "add", "src/main.py")
        run_git(repo, "commit", "-m", "initial code")
        initial = run_git(repo, "rev-parse", "HEAD").stdout.strip()

        path.write_text(
            "alpha = 1\n"
            "beta = 20\n"
            "gamma = 3\n"
            "delta = 4\n",
            encoding="utf-8",
        )
        run_git(repo, "add", "src/main.py")
        run_git(repo, "commit", "-m", "change beta")
        latest = run_git(repo, "rev-parse", "HEAD").stdout.strip()

        return repo, path, initial, latest

    def test_file_provenance_returns_latest_commit_touching_file(self):
        repo, _, _, latest = self.make_repo()

        provenance = capture_git_file_provenance(
            repo,
            "src/main.py",
        )

        self.assertIsNotNone(provenance)
        assert provenance is not None
        self.assertEqual(provenance.commit, latest)
        self.assertEqual(provenance.scope, "FILE")
        self.assertEqual(provenance.path, "src/main.py")
        self.assertIsNone(provenance.line_start)
        self.assertIsNone(provenance.line_end)

    def test_line_range_provenance_finds_latest_relevant_commit(self):
        repo, _, initial, latest = self.make_repo()

        changed = capture_git_file_provenance(
            repo,
            "src/main.py",
            line_start=2,
            line_end=2,
        )
        unchanged = capture_git_file_provenance(
            repo,
            "src/main.py",
            line_start=4,
            line_end=4,
        )

        self.assertIsNotNone(changed)
        self.assertIsNotNone(unchanged)
        assert changed is not None
        assert unchanged is not None

        self.assertEqual(changed.scope, "LINE_RANGE")
        self.assertEqual(changed.commit, latest)
        self.assertEqual(changed.line_start, 2)
        self.assertEqual(changed.line_end, 2)

        self.assertEqual(unchanged.scope, "LINE_RANGE")
        self.assertEqual(unchanged.commit, initial)

    def test_absolute_path_inside_repo_is_normalized(self):
        repo, path, _, latest = self.make_repo()

        provenance = capture_git_file_provenance(
            repo,
            path,
        )

        self.assertIsNotNone(provenance)
        assert provenance is not None
        self.assertEqual(provenance.path, "src/main.py")
        self.assertEqual(provenance.commit, latest)

    def test_untracked_file_returns_none(self):
        repo, _, _, _ = self.make_repo()
        path = repo / "src" / "untracked.py"
        path.write_text("print('new')\n", encoding="utf-8")

        provenance = capture_git_file_provenance(
            repo,
            "src/untracked.py",
        )

        self.assertIsNone(provenance)

    def test_path_outside_repo_is_rejected(self):
        repo, _, _, _ = self.make_repo()

        with tempfile.TemporaryDirectory() as td:
            outside = Path(td) / "outside.py"
            outside.write_text("x=1\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                capture_git_file_provenance(
                    repo,
                    outside,
                )

    def test_invalid_line_range_is_rejected(self):
        repo, _, _, _ = self.make_repo()

        with self.assertRaises(ValueError):
            capture_git_file_provenance(
                repo,
                "src/main.py",
                line_start=2,
            )
        with self.assertRaises(ValueError):
            capture_git_file_provenance(
                repo,
                "src/main.py",
                line_start=3,
                line_end=2,
            )

    def test_non_repository_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GitProvenanceError):
                capture_git_file_provenance(
                    td,
                    "file.py",
                )

    def test_attach_preserves_head_and_adds_provenance_commit(self):
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="src/main.py",
            git_branch="rag-test",
            git_commit="a" * 40,
        )
        provenance = GitFileProvenance(
            repository_root="C:/repo",
            path="src/main.py",
            commit="b" * 40,
            scope="FILE",
        )

        attached = attach_git_provenance_to_metadata(
            metadata,
            provenance,
        )

        self.assertEqual(attached.git_branch, "rag-test")
        self.assertEqual(attached.git_commit, "a" * 40)
        self.assertEqual(
            attached.git_provenance_commit,
            "b" * 40,
        )
        self.assertIsNone(metadata.git_provenance_commit)

    def test_attach_line_provenance_to_matching_chunk(self):
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="beta = 20",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src/main.py",
                line_start=2,
                line_end=2,
                git_branch="rag-test",
                git_commit="a" * 40,
            ),
            ordinal=0,
        )
        provenance = GitFileProvenance(
            repository_root="C:/repo",
            path="src/main.py",
            commit="b" * 40,
            scope="LINE_RANGE",
            line_start=2,
            line_end=2,
        )

        attached = attach_git_provenance_to_chunk(
            chunk,
            provenance,
        )

        self.assertEqual(
            attached.metadata.git_provenance_commit,
            "b" * 40,
        )
        self.assertEqual(attached.metadata.git_commit, "a" * 40)
        self.assertIsNone(chunk.metadata.git_provenance_commit)

    def test_mismatched_chunk_range_is_rejected(self):
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="beta = 20",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src/main.py",
                line_start=2,
                line_end=2,
            ),
            ordinal=0,
        )
        provenance = GitFileProvenance(
            repository_root="C:/repo",
            path="src/main.py",
            commit="b" * 40,
            scope="LINE_RANGE",
            line_start=3,
            line_end=3,
        )

        with self.assertRaises(ValueError):
            attach_git_provenance_to_chunk(
                chunk,
                provenance,
            )

    def test_mismatched_path_is_rejected(self):
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="src/main.py",
        )
        provenance = GitFileProvenance(
            repository_root="C:/repo",
            path="src/other.py",
            commit="b" * 40,
            scope="FILE",
        )

        with self.assertRaises(ValueError):
            attach_git_provenance_to_metadata(
                metadata,
                provenance,
            )


if __name__ == "__main__":
    unittest.main()
