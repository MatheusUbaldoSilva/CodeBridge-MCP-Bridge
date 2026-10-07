import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.sources.git_worktree import (
    GitPathStatus,
    GitWorktreeError,
    attach_git_path_state_to_chunk,
    attach_git_path_state_to_metadata,
    capture_git_path_state,
)


def run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class RagGitWorktreeStateTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "repo"
        repo.mkdir()

        run_git(repo, "init", "-b", "rag-test")
        run_git(repo, "config", "user.email", "rag@example.test")
        run_git(repo, "config", "user.name", "RAG Test")

        path = repo / "tracked.txt"
        path.write_text("alpha\n", encoding="utf-8")
        run_git(repo, "add", "tracked.txt")
        run_git(repo, "commit", "-m", "initial")

        return repo, path

    def test_clean_tracked_file(self):
        repo, _ = self.make_repo()

        state = capture_git_path_state(repo, "tracked.txt")

        self.assertEqual(state.status, GitPathStatus.CLEAN)
        self.assertFalse(state.dirty)
        self.assertEqual(state.index_code, " ")
        self.assertEqual(state.worktree_code, " ")

    def test_unstaged_modified_file(self):
        repo, path = self.make_repo()
        path.write_text("beta\n", encoding="utf-8")

        state = capture_git_path_state(repo, "tracked.txt")

        self.assertEqual(state.status, GitPathStatus.MODIFIED)
        self.assertTrue(state.dirty)
        self.assertEqual(state.index_code, " ")
        self.assertEqual(state.worktree_code, "M")

    def test_staged_modified_file(self):
        repo, path = self.make_repo()
        path.write_text("beta\n", encoding="utf-8")
        run_git(repo, "add", "tracked.txt")

        state = capture_git_path_state(repo, "tracked.txt")

        self.assertEqual(state.status, GitPathStatus.STAGED)
        self.assertTrue(state.dirty)
        self.assertEqual(state.index_code, "M")
        self.assertEqual(state.worktree_code, " ")

    def test_staged_and_modified_file(self):
        repo, path = self.make_repo()
        path.write_text("beta\n", encoding="utf-8")
        run_git(repo, "add", "tracked.txt")
        path.write_text("gamma\n", encoding="utf-8")

        state = capture_git_path_state(repo, "tracked.txt")

        self.assertEqual(
            state.status,
            GitPathStatus.STAGED_AND_MODIFIED,
        )
        self.assertEqual(state.index_code, "M")
        self.assertEqual(state.worktree_code, "M")

    def test_untracked_file(self):
        repo, _ = self.make_repo()
        path = repo / "new.txt"
        path.write_text("new\n", encoding="utf-8")

        state = capture_git_path_state(repo, "new.txt")

        self.assertEqual(state.status, GitPathStatus.UNTRACKED)
        self.assertTrue(state.dirty)
        self.assertEqual(state.raw_status[:2], "??")

    def test_deleted_file(self):
        repo, path = self.make_repo()
        path.unlink()

        state = capture_git_path_state(repo, "tracked.txt")

        self.assertEqual(state.status, GitPathStatus.DELETED)
        self.assertTrue(state.dirty)

    def test_absolute_path_inside_repo_is_supported(self):
        repo, path = self.make_repo()

        state = capture_git_path_state(repo, path)

        self.assertEqual(state.path, "tracked.txt")
        self.assertEqual(state.status, GitPathStatus.CLEAN)

    def test_outside_path_is_rejected(self):
        repo, _ = self.make_repo()
        with tempfile.TemporaryDirectory() as td:
            outside = Path(td) / "outside.txt"
            outside.write_text("x\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                capture_git_path_state(repo, outside)

    def test_non_repository_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GitWorktreeError):
                capture_git_path_state(td, "file.txt")

    def test_attach_state_preserves_git_history_fields(self):
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="tracked.txt",
            git_branch="rag-test",
            git_commit="a" * 40,
            git_provenance_commit="b" * 40,
        )
        repo, path = self.make_repo()
        path.write_text("changed\n", encoding="utf-8")
        state = capture_git_path_state(repo, "tracked.txt")

        attached = attach_git_path_state_to_metadata(metadata, state)

        self.assertEqual(
            attached.git_worktree_status,
            GitPathStatus.MODIFIED.value,
        )
        self.assertEqual(attached.git_branch, "rag-test")
        self.assertEqual(attached.git_commit, "a" * 40)
        self.assertEqual(
            attached.git_provenance_commit,
            "b" * 40,
        )
        self.assertIsNone(metadata.git_worktree_status)

    def test_attach_to_chunk_is_immutable(self):
        repo, path = self.make_repo()
        path.write_text("changed\n", encoding="utf-8")
        state = capture_git_path_state(repo, "tracked.txt")
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="alpha",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="tracked.txt",
            ),
            ordinal=0,
        )

        attached = attach_git_path_state_to_chunk(chunk, state)

        self.assertEqual(
            attached.metadata.git_worktree_status,
            "MODIFIED",
        )
        self.assertIsNone(chunk.metadata.git_worktree_status)

    def test_path_conflict_is_rejected(self):
        repo, _ = self.make_repo()
        state = capture_git_path_state(repo, "tracked.txt")
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="other.txt",
        )

        with self.assertRaises(ValueError):
            attach_git_path_state_to_metadata(metadata, state)


if __name__ == "__main__":
    unittest.main()
