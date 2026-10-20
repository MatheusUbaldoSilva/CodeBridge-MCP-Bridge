"""V1.03-D-A read-only gate for future commit-triggered RAG jobs.

No worker, watcher, timer, persistent queue, or index mutation is performed.
A future scheduled worker must revalidate this exact scope at claim time.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Iterable

from rag.chunking.provenance import source_sha256
from rag.runtime.index_request import RagIndexScope, plan_rag_index


_SHA = re.compile(r"^[0-9a-f]{40}$")
_CONTENT = re.compile(r"^[0-9a-f]{64}$")


def assess_commit_index_event(
    project_root: str | Path,
    source_path: str,
    *,
    approved_paths: Iterable[str] = (),
    observed_commit: str = "",
    observed_sha256: str = "",
    changed_at_epoch: float = 0,
    now_epoch: float | None = None,
    debounce_seconds: float = 30,
    indexing_enabled: bool = False,
) -> dict:
    def report(state: str, **details):
        return {
            "state": state, "project_id": "codebridge",
            "source_path": source_path,
            "read_only": True, "queued": False,
            "executed": False, "safe_to_publish": False,
            **details,
        }

    if indexing_enabled is not True:
        return report("AUTO_INDEX_DISABLED")
    root = Path(project_root).resolve(strict=True)
    if root.name != "CodeBridge-MCP-Bridge" or not (root / ".git").exists():
        return report("UNAPPROVED_PROJECT_ROOT")
    if not isinstance(source_path, str) or not source_path:
        return report("INVALID_SOURCE_PATH")
    posix = PurePosixPath(source_path)
    if (posix.is_absolute() or ".." in posix.parts or
            posix.as_posix() != source_path):
        return report("INVALID_SOURCE_PATH")
    if source_path not in frozenset(approved_paths):
        return report("SOURCE_NOT_APPROVED")
    path = (root / Path(*posix.parts)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return report("SOURCE_MISSING_OR_ESCAPED")
    if not (_SHA.fullmatch(observed_commit) and _CONTENT.fullmatch(observed_sha256)):
        return report("INVALID_COMMIT_OR_SHA")
    if not 0 <= debounce_seconds <= 3600 or changed_at_epoch < 0:
        return report("INVALID_STABILITY_CONTRACT")
    now = time.time() if now_epoch is None else float(now_epoch)
    if now < changed_at_epoch:
        return report("INVALID_STABILITY_CONTRACT")

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True, capture_output=True, text=True, timeout=10,
        )
        return completed.stdout.strip()

    try:
        head = git("rev-parse", "HEAD")
        if head != observed_commit:
            return report("COMMIT_SUPERSEDED", head=head)
        if git("status", "--porcelain", "--", source_path):
            return report("SOURCE_NOT_COMMITTED")
        plan = plan_rag_index(
            "codebridge", root, scope=RagIndexScope.BOTH,
            paths=(source_path,),
        )
        if plan.candidate_count != 1 or plan.denied_count or plan.sensitive_count:
            return report(
                "SOURCE_DENIED_OR_UNSUPPORTED",
                denied_count=plan.denied_count,
                sensitive_count=plan.sensitive_count,
            )
        current_sha = source_sha256(path.read_text(
            encoding="utf-8", errors="replace",
        ))
        if current_sha != observed_sha256:
            return report("CONTENT_SHA_CHANGED")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return report("SOURCE_VALIDATION_FAILED")
    due = changed_at_epoch + debounce_seconds
    if now < due:
        return report(
            "AWAITING_STABLE_COMMIT",
            candidate_sha256=current_sha, head=head,
            ready_at_epoch=due,
        )
    return report(
        "ELIGIBLE_FOR_DURABLE_QUEUE",
        candidate_sha256=current_sha, head=head,
        ready_at_epoch=due,
        eligible_text=plan.text_candidate_count == 1,
        eligible_code=plan.code_candidate_count == 1,
        worker_available=False,
    )
