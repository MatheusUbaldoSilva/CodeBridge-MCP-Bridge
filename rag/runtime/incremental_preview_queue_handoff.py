"""Immutable advisory handoff between P8 source preview and durable job queue.

No SQLite connections, queue writes, worker activation, or index mutation.
The real queue MUST recheck Git, content SHA, debounce and approval at enqueue.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
import re


_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def prepare_preview_queue_handoff(preview: dict, *, approved_paths: tuple[str, ...]) -> dict:
    def blocked(reason: str) -> dict:
        return {
            "state": "HANDOFF_BLOCKED", "reason": reason, "intents": [],
            "queued": False, "worker_started": False,
            "active_index_updated": False, "safe_to_publish": False,
            "must_revalidate_at_enqueue": True,
        }

    if (not isinstance(preview, dict)
            or preview.get("state") != "EXPLICIT_SOURCE_PREVIEW_ONLY"
            or preview.get("read_only") is not True
            or preview.get("queued") is not False
            or preview.get("safe_to_publish") is not False):
        return blocked("UNVERIFIED_SOURCE_PREVIEW")
    if (not isinstance(approved_paths, tuple) or not approved_paths
            or len(approved_paths) > 32 or any(
                not isinstance(item, str) or not item for item in approved_paths
            ) or len(set(approved_paths)) != len(approved_paths)):
        return blocked("INVALID_EXPLICIT_APPROVALS")
    for item in approved_paths:
        path = PurePosixPath(item)
        if (path.is_absolute() or ".." in path.parts or
                path.as_posix() != item or any(ch in item for ch in "\\*?[]")
                or item in (".", "..")):
            return blocked("INVALID_EXPLICIT_APPROVALS")
    generation = preview.get("public_generation")
    if not isinstance(generation, str) or not (
            generation == "legacy" or re.fullmatch(r"v1_delta_[0-9a-f]{14}", generation)):
        return blocked("PUBLIC_GENERATION_UNVERIFIED")
    head = preview.get("observed_commit")
    candidate_list = preview.get("candidates")
    if (not isinstance(head, str) or not _COMMIT.fullmatch(head)
            or not isinstance(candidate_list, list)
            or len(candidate_list) != len(approved_paths)):
        return blocked("PREVIEW_COMMIT_OR_CARDINALITY_INVALID")
    candidates = {item.get("path"): item for item in candidate_list
                  if isinstance(item, dict) and isinstance(item.get("path"), str)}
    if len(candidates) != len(approved_paths) or set(candidates) != set(approved_paths):
        return blocked("PREVIEW_SCOPE_MISMATCH")
    intents = []
    for path in approved_paths:
        candidate = candidates[path]
        sha = candidate.get("sha256")
        if (candidate.get("state") != "ELIGIBLE_FOR_DURABLE_QUEUE"
                or candidate.get("intent") not in ("INDEX_NEW", "REINDEX_CHANGED")
                or candidate.get("head") != head
                or not isinstance(sha, str) or not _SHA256.fullmatch(sha)):
            return blocked("SOURCE_NOT_READY_FOR_REVALIDATION")
        job_key = hashlib.sha256(
            ("codebridge\0" + path + "\0" + head + "\0" + sha).encode("utf-8")
        ).hexdigest()
        intents.append({
            "project_id": "codebridge", "source_path": path,
            "observed_commit": head, "observed_sha256": sha,
            "purpose": candidate["intent"], "prospective_job_id": job_key,
            "requires_fresh_gate_at_enqueue": True,
        })
    return {
        "state": "ADVISORY_QUEUE_INTENTS_PREPARED",
        "public_generation_at_preview": generation,
        "intents": intents, "queued": False, "worker_started": False,
        "active_index_updated": False, "safe_to_publish": False,
        "must_revalidate_at_enqueue": True,
    }
