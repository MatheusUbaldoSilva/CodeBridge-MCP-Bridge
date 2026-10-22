"""Read-only, explicit per-source preview before durable incremental enqueue.

No automatic approvals, event generation, queue mutation or watcher.
"""
from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import time

from rag.chunking.provenance import source_sha256
from rag.runtime.incremental_installed_change_discovery import discover_installed_reindex_scope
from rag.runtime.incremental_job_prequeue import assess_commit_index_event
from rag.runtime.incremental_scheduler_public_pointer import inspect_public_pointer_for_scheduler
from rag.runtime.status import resolve_rag_sqlite_path


def preview_approved_unindexed_sources(
    project_root: str | Path, *, approved_paths: tuple[str, ...] = (),
    changed_at_epoch: float | None = None, debounce_seconds: float = 30,
    now_epoch: float | None = None,
) -> dict:
    def result(state, **fields):
        return {"state": state, "read_only": True, "queued": False,
                "worker_started": False, "active_index_updated": False,
                "safe_to_publish": False, **fields}

    if not approved_paths or changed_at_epoch is None:
        return result("SOURCE_APPROVAL_AND_OBSERVATION_REQUIRED", candidates=[])
    if (not isinstance(approved_paths, tuple)
            or len(approved_paths) > 32
            or any(not isinstance(p, str) for p in approved_paths)
            or len(set(approved_paths)) != len(approved_paths)):
        return result("INVALID_EXPLICIT_SOURCE_SCOPE", candidates=[])
    numeric = (changed_at_epoch, debounce_seconds)
    if now_epoch is not None:
        numeric += (now_epoch,)
    if (any(type(v) not in (float, int) or not math.isfinite(v) for v in numeric)
            or changed_at_epoch < 0 or not (0 <= debounce_seconds <= 3600)):
        return result("INVALID_OBSERVATION_TIME", candidates=[])
    root = Path(project_root).resolve()
    if root.name != "CodeBridge-MCP-Bridge" or not (root / ".git").exists():
        return result("UNAPPROVED_PROJECT_ROOT", candidates=[])
    for path in approved_paths:
        if (not isinstance(path, str) or not path
                or any(c in path for c in "*?[]\\")
                or PurePosixPath(path).as_posix() != path
                or PurePosixPath(path).is_absolute()
                or ".." in PurePosixPath(path).parts
                or Path(path).is_absolute()):
            return result("INVALID_EXPLICIT_SOURCE_SCOPE", candidates=[])

    observed = discover_installed_reindex_scope(root)
    if observed["state"] not in ("INDEXED_SOURCES_CURRENT", "INDEXED_SOURCES_DRIFT_FOUND"):
        return result("INSTALLED_SOURCE_SNAPSHOT_UNVERIFIED", candidates=[])
    pointer = inspect_public_pointer_for_scheduler()
    if pointer["state"] not in ("PUBLIC_POINTER_OBSERVED", "PUBLIC_LEGACY_POINTER"):
        return result("PUBLIC_POINTER_UNVERIFIED", candidates=[])
    installed = resolve_rag_sqlite_path().resolve().parent
    generation = (
        installed if pointer["generation"] == "legacy"
        else installed / "generations" / pointer["generation"]
    )
    try:
        manifest = json.loads((generation / "rag-index-manifest.json").read_text(encoding="utf-8"))
        indexed = {row["path"] for row in manifest["entries"] if row["project_id"] == "codebridge"}
        before = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", before) is None:
            return result("GIT_REVISION_UNVERIFIED", candidates=[])
        now = time.time() if now_epoch is None else now_epoch
        candidates = []
        for path in approved_paths:
            if path in indexed:
                candidates.append({"path": path, "state": "ALREADY_INDEXED"})
                continue
            file = (root / Path(*PurePosixPath(path).parts)).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                candidates.append({"path": path, "state": "SOURCE_MISSING_OR_ESCAPED"})
                continue
            sha = source_sha256(file.read_text(encoding="utf-8", errors="replace"))
            gate = assess_commit_index_event(
                root, path, approved_paths=approved_paths,
                observed_commit=before, observed_sha256=sha,
                changed_at_epoch=changed_at_epoch, now_epoch=now,
                debounce_seconds=debounce_seconds, indexing_enabled=True,
            )
            candidates.append({"path": path, "state": gate["state"],
                               "head": gate.get("head"),
                               "sha256": gate.get("candidate_sha256")})
        after = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        if after != before or inspect_public_pointer_for_scheduler() != pointer:
            return result("SNAPSHOT_CHANGED_DURING_PREVIEW", candidates=[])
        return result("EXPLICIT_SOURCE_PREVIEW_ONLY",
                      public_generation=pointer["generation"],
                      observed_commit=before, candidates=candidates)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return result("SOURCE_PREVIEW_FAILED", candidates=[])
