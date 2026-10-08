"""Explicit RAG indexing request contract for RAG-013-B.

Planning is read-only and deterministic.
Heavy indexing can run only when execute=True and an executor is explicitly
provided by the embedding/index runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Optional, Tuple

from rag.index.vector_namespace import require_project_namespace
from rag.sources.code_inventory import is_code_source
from rag.sources.document_inventory import is_document_source
from rag.sources.exclusion_policy import classify_denied_path


class RagIndexScope(str, Enum):
    TEXT = "TEXT"
    CODE = "CODE"
    BOTH = "BOTH"


class RagIndexAction(str, Enum):
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"


class RagIndexExecutionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RagIndexCandidate:
    path: str
    text_eligible: bool
    code_eligible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path:
            raise ValueError("path must be non-empty")
        if not self.text_eligible and not self.code_eligible:
            raise ValueError("candidate must be eligible for at least one index")


@dataclass(frozen=True)
class RagIndexPlan:
    project_id: str
    project_root: str
    scope: RagIndexScope
    candidates: Tuple[RagIndexCandidate, ...]
    denied_count: int
    unsupported_count: int

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def text_candidate_count(self) -> int:
        return sum(item.text_eligible for item in self.candidates)

    @property
    def code_candidate_count(self) -> int:
        return sum(item.code_eligible for item in self.candidates)

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "project_root": self.project_root,
            "scope": self.scope.value,
            "candidate_count": self.candidate_count,
            "text_candidate_count": self.text_candidate_count,
            "code_candidate_count": self.code_candidate_count,
            "denied_count": self.denied_count,
            "unsupported_count": self.unsupported_count,
            "candidates": [
                {
                    "path": item.path,
                    "text_eligible": item.text_eligible,
                    "code_eligible": item.code_eligible,
                }
                for item in self.candidates
            ],
        }


@dataclass(frozen=True)
class RagIndexOperationResult:
    action: RagIndexAction
    executed: bool
    plan: RagIndexPlan
    execution: Optional[dict[str, object]] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "executed": self.executed,
            "plan": self.plan.to_dict(),
            "execution": (
                dict(self.execution)
                if self.execution is not None
                else None
            ),
        }


RagIndexExecutor = Callable[[RagIndexPlan], dict[str, object]]


def _canonical_relative_path(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(root.resolve())
    value = PurePosixPath(relative.as_posix())
    if ".." in value.parts:
        raise ValueError("candidate path escapes project root")
    return str(value)


def _scope_accepts(
    scope: RagIndexScope,
    *,
    text_eligible: bool,
    code_eligible: bool,
) -> bool:
    if scope is RagIndexScope.TEXT:
        return text_eligible
    if scope is RagIndexScope.CODE:
        return code_eligible
    return text_eligible or code_eligible


def plan_rag_index(
    project_id: str,
    project_root: str | Path,
    *,
    scope: RagIndexScope = RagIndexScope.BOTH,
    paths: Iterable[str] = (),
) -> RagIndexPlan:
    project = require_project_namespace(project_id)
    if not isinstance(scope, RagIndexScope):
        raise ValueError("scope must be RagIndexScope")

    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("project_root must be an existing directory")

    requested = tuple(paths)
    if any(not isinstance(item, str) or not item.strip() for item in requested):
        raise ValueError("paths must contain non-empty relative paths")

    if requested:
        filesystem_paths = []
        for raw in requested:
            candidate = (root / raw).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError("path must stay inside project_root") from exc
            if candidate.is_file():
                filesystem_paths.append(candidate)
            elif candidate.is_dir():
                filesystem_paths.extend(
                    item
                    for item in candidate.rglob("*")
                    if item.is_file()
                )
            else:
                raise ValueError(f"path does not exist: {raw}")
    else:
        filesystem_paths = [
            item
            for item in root.rglob("*")
            if item.is_file()
        ]

    candidates = []
    denied_count = 0
    unsupported_count = 0
    seen = set()

    for file_path in sorted(filesystem_paths):
        relative = _canonical_relative_path(root, file_path)
        if relative in seen:
            continue
        seen.add(relative)

        if classify_denied_path(relative) is not None:
            denied_count += 1
            continue

        text_eligible = is_document_source(relative)
        code_eligible = is_code_source(relative)

        if not _scope_accepts(
            scope,
            text_eligible=text_eligible,
            code_eligible=code_eligible,
        ):
            unsupported_count += 1
            continue

        candidates.append(
            RagIndexCandidate(
                path=relative,
                text_eligible=(
                    text_eligible
                    and scope in {RagIndexScope.TEXT, RagIndexScope.BOTH}
                ),
                code_eligible=(
                    code_eligible
                    and scope in {RagIndexScope.CODE, RagIndexScope.BOTH}
                ),
            )
        )

    return RagIndexPlan(
        project_id=project,
        project_root=str(root),
        scope=scope,
        candidates=tuple(candidates),
        denied_count=denied_count,
        unsupported_count=unsupported_count,
    )


def run_explicit_rag_index(
    project_id: str,
    project_root: str | Path,
    *,
    scope: RagIndexScope = RagIndexScope.BOTH,
    paths: Iterable[str] = (),
    execute: bool = False,
    executor: Optional[RagIndexExecutor] = None,
) -> RagIndexOperationResult:
    plan = plan_rag_index(
        project_id,
        project_root,
        scope=scope,
        paths=paths,
    )

    if not execute:
        return RagIndexOperationResult(
            action=RagIndexAction.PLAN,
            executed=False,
            plan=plan,
            execution=None,
        )

    if executor is None:
        raise RagIndexExecutionUnavailableError(
            "explicit indexing was requested but no RAG index executor is registered"
        )

    payload = executor(plan)
    if not isinstance(payload, dict):
        raise ValueError("executor must return a dict")

    return RagIndexOperationResult(
        action=RagIndexAction.EXECUTE,
        executed=True,
        plan=plan,
        execution=dict(payload),
    )
