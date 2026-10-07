"""Read-only Git HEAD/branch capture for RAG-011-A."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import subprocess
from typing import Callable, Optional, Sequence

from rag.contracts import Chunk, SourceMetadata


_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHeadState:
    repository_root: str
    head_commit: str
    branch: Optional[str]
    detached: bool

    def __post_init__(self) -> None:
        if not isinstance(self.repository_root, str) or not self.repository_root.strip():
            raise ValueError("repository_root must be non-empty")
        if not isinstance(self.head_commit, str) or not _GIT_COMMIT_RE.fullmatch(
            self.head_commit
        ):
            raise ValueError("head_commit must be a 40-character lowercase Git SHA")
        if self.detached:
            if self.branch is not None:
                raise ValueError("detached state must not expose branch")
        else:
            if not isinstance(self.branch, str) or not self.branch.strip():
                raise ValueError("attached state requires branch")


def _run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    runner: Runner,
) -> str:
    command = ["git", "-C", str(cwd), *args]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitStateError(
            f"failed to execute Git: {type(exc).__name__}: {exc}"
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitStateError(
            f"Git command failed ({' '.join(args)}): {detail or 'unknown error'}"
        )

    return (completed.stdout or "").strip()


def capture_git_head_state(
    repository: str | Path,
    *,
    runner: Runner = subprocess.run,
) -> GitHeadState:
    """Capture repository root, HEAD and current branch without mutation."""

    candidate = Path(repository).expanduser().resolve()

    root_raw = _run_git(
        ("rev-parse", "--show-toplevel"),
        cwd=candidate,
        runner=runner,
    )
    root = Path(root_raw).resolve()

    head = _run_git(
        ("rev-parse", "HEAD"),
        cwd=root,
        runner=runner,
    ).lower()

    if not _GIT_COMMIT_RE.fullmatch(head):
        raise GitStateError("Git HEAD did not return a canonical 40-character SHA")

    branch = _run_git(
        ("branch", "--show-current"),
        cwd=root,
        runner=runner,
    )
    branch_value = branch or None

    return GitHeadState(
        repository_root=str(root),
        head_commit=head,
        branch=branch_value,
        detached=branch_value is None,
    )


def attach_git_head_state_to_metadata(
    metadata: SourceMetadata,
    state: GitHeadState,
) -> SourceMetadata:
    if not isinstance(metadata, SourceMetadata):
        raise ValueError("metadata must be SourceMetadata")
    if not isinstance(state, GitHeadState):
        raise ValueError("state must be GitHeadState")

    return replace(
        metadata,
        git_branch=state.branch,
        git_commit=state.head_commit,
    )


def attach_git_head_state_to_chunk(
    chunk: Chunk,
    state: GitHeadState,
) -> Chunk:
    if not isinstance(chunk, Chunk):
        raise ValueError("chunk must be Chunk")
    if not isinstance(state, GitHeadState):
        raise ValueError("state must be GitHeadState")

    return replace(
        chunk,
        metadata=attach_git_head_state_to_metadata(
            chunk.metadata,
            state,
        ),
    )
