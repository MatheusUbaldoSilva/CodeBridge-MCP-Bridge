"""Read-only Git working-tree path state capture for RAG-011-C."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
import subprocess

from rag.contracts import Chunk, SourceMetadata
from rag.sources.git_state import GitStateError, capture_git_head_state


class GitWorktreeError(RuntimeError):
    pass


class GitPathStatus(str, Enum):
    CLEAN = "CLEAN"
    MODIFIED = "MODIFIED"
    STAGED = "STAGED"
    STAGED_AND_MODIFIED = "STAGED_AND_MODIFIED"
    UNTRACKED = "UNTRACKED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    TYPE_CHANGED = "TYPE_CHANGED"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True)
class GitPathState:
    repository_root: str
    path: str
    status: GitPathStatus
    index_code: str
    worktree_code: str
    raw_status: str

    @property
    def dirty(self) -> bool:
        return self.status is not GitPathStatus.CLEAN


def _canonical_repo_path(root: Path, path: str | Path) -> str:
    raw = str(path).strip()
    if not raw:
        raise ValueError("path must be non-empty")
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("path must stay inside repository_root") from exc
    else:
        relative = candidate
    normalized = PurePosixPath(str(relative).replace("\\", "/"))
    parts = tuple(part for part in normalized.parts if part != ".")
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path must stay inside repository_root")
    return "/".join(parts)


def _classify_xy(index_code: str, worktree_code: str) -> GitPathStatus:
    pair = f"{index_code}{worktree_code}"
    if pair == "??":
        return GitPathStatus.UNTRACKED
    if pair in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"} or "U" in pair:
        return GitPathStatus.CONFLICTED
    if "R" in pair or "C" in pair:
        return GitPathStatus.RENAMED
    if "D" in pair:
        return GitPathStatus.DELETED
    if "T" in pair:
        return GitPathStatus.TYPE_CHANGED
    staged = index_code not in {" ", "?"}
    modified = worktree_code not in {" ", "?"}
    if staged and modified:
        return GitPathStatus.STAGED_AND_MODIFIED
    if staged:
        return GitPathStatus.STAGED
    if modified:
        return GitPathStatus.MODIFIED
    return GitPathStatus.CLEAN


def capture_git_path_state(
    repository: str | Path,
    path: str | Path,
) -> GitPathState:
    try:
        head_state = capture_git_head_state(repository)
    except GitStateError as exc:
        raise GitWorktreeError(str(exc)) from exc

    root = Path(head_state.repository_root)
    relative_path = _canonical_repo_path(root, path)
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            relative_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitWorktreeError(
            f"Git status failed for {relative_path}: {detail or 'unknown error'}"
        )

    lines = [line for line in (completed.stdout or "").splitlines() if line]
    if not lines:
        return GitPathState(
            repository_root=str(root),
            path=relative_path,
            status=GitPathStatus.CLEAN,
            index_code=" ",
            worktree_code=" ",
            raw_status="",
        )
    if len(lines) != 1:
        raise GitWorktreeError(
            f"expected one Git status entry for {relative_path}, got {len(lines)}"
        )

    raw = lines[0]
    if len(raw) < 2:
        raise GitWorktreeError(f"invalid porcelain status for {relative_path}")

    index_code = raw[0]
    worktree_code = raw[1]
    return GitPathState(
        repository_root=str(root),
        path=relative_path,
        status=_classify_xy(index_code, worktree_code),
        index_code=index_code,
        worktree_code=worktree_code,
        raw_status=raw,
    )


def attach_git_path_state_to_metadata(
    metadata: SourceMetadata,
    state: GitPathState,
) -> SourceMetadata:
    if not isinstance(metadata, SourceMetadata):
        raise ValueError("metadata must be SourceMetadata")
    if not isinstance(state, GitPathState):
        raise ValueError("state must be GitPathState")
    if metadata.path is not None:
        metadata_path = PurePosixPath(metadata.path.replace("\\", "/"))
        if metadata_path != PurePosixPath(state.path):
            raise ValueError("metadata path conflicts with Git worktree path")
    return replace(
        metadata,
        git_worktree_status=state.status.value,
    )


def attach_git_path_state_to_chunk(
    chunk: Chunk,
    state: GitPathState,
) -> Chunk:
    if not isinstance(chunk, Chunk):
        raise ValueError("chunk must be Chunk")
    return replace(
        chunk,
        metadata=attach_git_path_state_to_metadata(chunk.metadata, state),
    )
