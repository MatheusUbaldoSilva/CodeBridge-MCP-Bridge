import subprocess
import tempfile
import unittest
from pathlib import Path

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.sources.git_state import (
    GitHeadState,
    GitStateError,
    attach_git_head_state_to_chunk,
    attach_git_head_state_to_metadata,
    capture_git_head_state,
)


def run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class RagGitHeadStateTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "repo"
        repo.mkdir()

        run_git(repo, "init", "-b", "rag-test")
        run_git(repo, "config", "user.email", "rag@example.test")
        run_git(repo, "config", "user.name", "RAG Test")

        tracked = repo / "tracked.txt"
        tracked.write_text("hello\n", encoding="utf-8")
        run_git(repo, "add", "tracked.txt")
        run_git(repo, "commit", "-m", "initial")

        return repo

    def test_capture_attached_head_and_branch(self):
        repo = self.make_repo()

        state = capture_git_head_state(repo)

        expected_head = run_git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()

        self.assertEqual(state.branch, "rag-test")
        self.assertFalse(state.detached)
        self.assertEqual(state.head_commit, expected_head)
        self.assertEqual(
            Path(state.repository_root).resolve(),
            repo.resolve(),
        )

    def test_capture_from_subdirectory_resolves_repository_root(self):
        repo = self.make_repo()
        nested = repo / "a" / "b"
        nested.mkdir(parents=True)

        state = capture_git_head_state(nested)

        self.assertEqual(
            Path(state.repository_root).resolve(),
            repo.resolve(),
        )
        self.assertEqual(state.branch, "rag-test")

    def test_detached_head_is_explicit(self):
        repo = self.make_repo()
        head = run_git(repo, "rev-parse", "HEAD").stdout.strip()
        run_git(repo, "checkout", "--detach", head)

        state = capture_git_head_state(repo)

        self.assertTrue(state.detached)
        self.assertIsNone(state.branch)
        self.assertEqual(state.head_commit, head)

    def test_non_repository_is_structured_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GitStateError):
                capture_git_head_state(td)

    def test_attach_state_to_metadata(self):
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
            path="src/main.py",
        )
        state = GitHeadState(
            repository_root="C:/repo",
            head_commit="a" * 40,
            branch="main",
            detached=False,
        )

        attached = attach_git_head_state_to_metadata(
            metadata,
            state,
        )

        self.assertIsNone(metadata.git_branch)
        self.assertIsNone(metadata.git_commit)
        self.assertEqual(attached.git_branch, "main")
        self.assertEqual(attached.git_commit, "a" * 40)
        self.assertEqual(attached.path, "src/main.py")

    def test_attach_state_to_chunk_preserves_chunk_contract(self):
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="print('hello')",
            metadata=SourceMetadata(
                project_id="codebridge",
                source_type=SourceType.CODE,
                path="src/main.py",
            ),
            ordinal=3,
        )
        state = GitHeadState(
            repository_root="C:/repo",
            head_commit="b" * 40,
            branch="feature/rag",
            detached=False,
        )

        attached = attach_git_head_state_to_chunk(
            chunk,
            state,
        )

        self.assertEqual(attached.chunk_id, chunk.chunk_id)
        self.assertEqual(attached.document_id, chunk.document_id)
        self.assertEqual(attached.content, chunk.content)
        self.assertEqual(attached.ordinal, chunk.ordinal)
        self.assertEqual(attached.metadata.git_branch, "feature/rag")
        self.assertEqual(attached.metadata.git_commit, "b" * 40)
        self.assertIsNone(chunk.metadata.git_branch)

    def test_detached_state_attaches_head_without_branch(self):
        metadata = SourceMetadata(
            project_id="codebridge",
            source_type=SourceType.CODE,
        )
        state = GitHeadState(
            repository_root="C:/repo",
            head_commit="c" * 40,
            branch=None,
            detached=True,
        )

        attached = attach_git_head_state_to_metadata(
            metadata,
            state,
        )

        self.assertIsNone(attached.git_branch)
        self.assertEqual(attached.git_commit, "c" * 40)

    def test_invalid_git_state_is_rejected(self):
        with self.assertRaises(ValueError):
            GitHeadState(
                repository_root="C:/repo",
                head_commit="short",
                branch="main",
                detached=False,
            )
        with self.assertRaises(ValueError):
            GitHeadState(
                repository_root="C:/repo",
                head_commit="d" * 40,
                branch="main",
                detached=True,
            )
        with self.assertRaises(ValueError):
            GitHeadState(
                repository_root="C:/repo",
                head_commit="d" * 40,
                branch=None,
                detached=False,
            )


if __name__ == "__main__":
    unittest.main()
