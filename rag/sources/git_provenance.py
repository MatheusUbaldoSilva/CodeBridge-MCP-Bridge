"""Read-only Git file/range provenance capture for RAG-011-B."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Callable, Optional, Sequence

from rag.contracts import Chunk, SourceMetadata
from rag.sources.git_state import GitHeadState, GitStateError, capture_git_head_state


_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitProvenanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitFileProvenance:
    repository_root: str
    path: str
    commit: str
    scope: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.repository_root, str) or not self.repository_root.strip():
            raise ValueError("repository_root must be non-empty")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be non-empty")
        if not _GIT_COMMIT_RE.fullmatch(self.commit):
            raise ValueError("commit must be a canonical 40-character Git SHA")
        if self.scope not in {"FILE", "LINE_RANGE"}:
            raise ValueError("scope must be FILE or LINE_RANGE")
        if self.scope == "FILE":
            if self.line_start is not None or self.line_end is not None:
                raise ValueError("FILE scope must not define a line range")
        else:
            if self.line_start is None or self.line_end is None:
                raise ValueError("LINE_RANGE scope requires line_start and line_end")
            if self.line_start < 1:
                raise ValueError("line_start must be >= 1")
            if self.line_end < self.line_start:
                raise ValueError("line_end must be >= line_start")


def _run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(cwd), *args]
    try:
        return runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitProvenanceError(
            f"failed to execute Git: {type(exc).__name__}: {exc}"
        ) from exc


def _canonical_repo_path(repository_root: Path, path: str | Path) -> str:
    raw = str(path).strip()
    if not raw:
        raise ValueError("path must be non-empty")

    candidate = Path(path)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ValueError("path must stay inside repository_root") from exc
    else:
        relative = candidate

    normalized = PurePosixPath(str(relative).replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("path must be relative to repository_root")
    parts = tuple(part for part in normalized.parts if part != ".")
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path must stay inside repository_root")
    return "/".join(parts)


def _extract_first_commit(output: str) -> Optional[str]:
    for line in (output or "").splitlines():
        value = line.strip().lower()
        if _GIT_COMMIT_RE.fullmatch(value):
            return value
    return None


def _capture_file_commit(
    repository_root: Path,
    relative_path: str,
    *,
    runner: Runner,
) -> Optional[str]:
    completed = _run_git(
        ("log", "-1", "--format=%H", "--", relative_path),
        cwd=repository_root,
        runner=runner,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitProvenanceError(
            f"Git file provenance failed for {relative_path}: "
            f"{detail or 'unknown error'}"
        )
    return _extract_first_commit(completed.stdout)


def _capture_line_commit(
    repository_root: Path,
    relative_path: str,
    line_start: int,
    line_end: int,
    *,
    runner: Runner,
) -> Optional[str]:
    completed = _run_git(
        (
            "log",
            "-1",
            "--format=%H",
            "-L",
            f"{line_start},{line_end}:{relative_path}",
        ),
        cwd=repository_root,
        runner=runner,
    )
    if completed.returncode != 0:
        return None
    return _extract_first_commit(completed.stdout)


def capture_git_file_provenance(
    repository: str | Path,
    path: str | Path,
    *,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    runner: Runner = subprocess.run,
) -> Optional[GitFileProvenance]:
    """Return latest relevant commit for a tracked file or line range.

    If a requested line-range lookup cannot be resolved, the operation falls
    back to the latest commit touching the file. Untracked files return None.
    """

    if (line_start is None) != (line_end is None):
        raise ValueError("line_start and line_end must be provided together")
    if line_start is not None:
        if not isinstance(line_start, int) or line_start < 1:
            raise ValueError("line_start must be an integer >= 1")
        if not isinstance(line_end, int) or line_end < line_start:
            raise ValueError("line_end must be an integer >= line_start")

    try:
        state = capture_git_head_state(repository, runner=runner)
    except GitStateError as exc:
        raise GitProvenanceError(str(exc)) from exc

    root = Path(state.repository_root)
    relative_path = _canonical_repo_path(root, path)

    if line_start is not None and line_end is not None:
        commit = _capture_line_commit(
            root,
            relative_path,
            line_start,
            line_end,
            runner=runner,
        )
        if commit is not None:
            return GitFileProvenance(
                repository_root=str(root),
                path=relative_path,
                commit=commit,
                scope="LINE_RANGE",
                line_start=line_start,
                line_end=line_end,
            )

    commit = _capture_file_commit(
        root,
        relative_path,
        runner=runner,
    )
    if commit is None:
        return None

    return GitFileProvenance(
        repository_root=str(root),
        path=relative_path,
        commit=commit,
        scope="FILE",
    )


def attach_git_provenance_to_metadata(
    metadata: SourceMetadata,
    provenance: GitFileProvenance,
) -> SourceMetadata:
    if not isinstance(metadata, SourceMetadata):
        raise ValueError("metadata must be SourceMetadata")
    if not isinstance(provenance, GitFileProvenance):
        raise ValueError("provenance must be GitFileProvenance")

    if metadata.path is not None:
        metadata_path = PurePosixPath(metadata.path.replace("\\", "/"))
        provenance_path = PurePosixPath(provenance.path)
        if metadata_path != provenance_path:
            raise ValueError(
                "metadata path conflicts with Git provenance path"
            )

    return replace(
        metadata,
        git_provenance_commit=provenance.commit,
    )


def attach_git_provenance_to_chunk(
    chunk: Chunk,
    provenance: GitFileProvenance,
) -> Chunk:
    if not isinstance(chunk, Chunk):
        raise ValueError("chunk must be Chunk")
    if not isinstance(provenance, GitFileProvenance):
        raise ValueError("provenance must be GitFileProvenance")

    if provenance.scope == "LINE_RANGE":
        if chunk.metadata.line_start is None or chunk.metadata.line_end is None:
            raise ValueError(
                "LINE_RANGE provenance requires chunk line metadata"
            )
        if (
            chunk.metadata.line_start != provenance.line_start
            or chunk.metadata.line_end != provenance.line_end
        ):
            raise ValueError(
                "chunk line range conflicts with Git provenance range"
            )

    return replace(
        chunk,
        metadata=attach_git_provenance_to_metadata(
            chunk.metadata,
            provenance,
        ),
    )
