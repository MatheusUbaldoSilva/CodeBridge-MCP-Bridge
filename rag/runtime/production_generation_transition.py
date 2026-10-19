"""Production CodeBridge RAG pointer transaction with conservative recovery.

Writes ONLY two small control files under the real RAG state root:
active-generation.json and production-generation-transition.json.
Never modifies, deletes, overwrites or relocates SQLite, Qdrant or generation
directories. All transitions require a cross-process exclusive generation lock.
The public reader refuses to read whenever a transition journal exists.

No publication is possible until assess_real_cutover returns READY and an
explicit, version-bound operator authorization is supplied.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from rag.runtime.status import resolve_rag_sqlite_path
from rag.runtime.production_generation_lock import production_generation_lock
from rag.runtime.production_generation_read import _read_pointer

JOURNAL_NAME = "production-generation-transition.json"
POINTER_NAME = "active-generation.json"
_GENERATION = re.compile(r"^v1_(?:base|delta)_[a-z0-9]{8,32}$")


class GenerationTransitionBlocked(RuntimeError):
    pass


def _root() -> Path:
    root = resolve_rag_sqlite_path().resolve().parent
    if root.name != "rag" or root.parent.name != "CodeBridge":
        raise GenerationTransitionBlocked("unexpected production RAG root")
    return root


def _atomic_json(target: Path, payload: dict[str, Any]) -> None:
    if target.name not in (JOURNAL_NAME, POINTER_NAME):
        raise GenerationTransitionBlocked("unapproved control filename")
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, delete=False,
            prefix=".generation-", suffix=".json.tmp",
        ) as handle:
            tmp = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        tmp = None
    finally:
        if tmp is not None:
            # Only discard a freshly generated temporary control file;
            # never delete durable journals or index data.
            tmp.unlink(missing_ok=True)


def _pointer_name(root: Path) -> str:
    found = _read_pointer(root)
    return "legacy" if found is None else found.generation


def _read_journal(root: Path) -> dict[str, Any] | None:
    journal = root / JOURNAL_NAME
    if not journal.exists():
        return None
    info = json.loads(journal.read_text(encoding="utf-8"))
    if (info.get("schema_version") != 1
            or info.get("previous") != "legacy"
            or not isinstance(info.get("candidate"), str)
            or not _GENERATION.fullmatch(info["candidate"])
            or info.get("state") != "PREPARED"):
        raise GenerationTransitionBlocked("unknown journal; manual investigation required")
    return info


def inspect_transition() -> dict[str, Any]:
    """Read-only overview; does not claim generation activation is safe."""
    with production_generation_lock(exclusive=False):
        root = _root()
        journal = _read_journal(root)
        return {
            "state": "RECOVERY_REQUIRED" if journal else "NO_PENDING_TRANSITION",
            "active": _pointer_name(root),
            "journal": journal,
            "safe_to_publish": False,
        }


def _verify_target_after_pointer(
    root: Path, candidate: str, expected: dict[str, Any],
) -> None:
    """Verify the switched immutable bundle using embedded MCP dependencies.

    This runs under the exclusive writer lock and leaves the transition
    journal intact if verification fails, so public readers remain blocked.
    """
    from rag.runtime.versioned_live_integrity import inspect_pinned_index
    from rag.runtime.production_generation_read import SearchStoragePaths

    folder = root / "generations" / candidate
    pinned = SearchStoragePaths(
        candidate,
        folder / "rag_index.sqlite3",
        folder / "qdrant",
        folder / "rag-index-manifest.json",
    )
    result = inspect_pinned_index(pinned)
    totals = {
        "documents": result["documents"],
        "chunks": result["chunks"],
        "vectors": sum(item["vectors"] for item in result["collections"].values()),
        "manifest_entries": result["manifest_entries"],
    }
    if any(totals[name] != expected.get(name) for name in totals):
        raise GenerationTransitionBlocked("post-switch bundle verification failed")


def publish_validated_generation(
    *, baseline: str, candidate: str, operator_authorization: str,
    public_reader_attestation: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed until live MCP reload is proven and gate explicitly READY.

    Recovery is ALWAYS journaled before pointer write. The legacy index
    remains physically untouched. Caller is responsible for independent
    post-publication semantic/public tool verification.
    """
    root = _root()
    if candidate == baseline or not _GENERATION.fullmatch(candidate):
        raise GenerationTransitionBlocked("invalid target generation")
    if operator_authorization != "CODEBRIDGE_RAG_V1_ACTIVATE:" + candidate:
        raise GenerationTransitionBlocked("explicit generation-specific approval required")
    if public_reader_attestation.get("generation_lock_enabled") is not True:
        raise GenerationTransitionBlocked("MCP readers not attested as locked")
    if public_reader_attestation.get("mcp_restart_confirmed") is not True:
        raise GenerationTransitionBlocked("public MCP safe restart has not been attested")
    # The current readiness gate intentionally returns BLOCKED until external
    # MCP verification, production rollback tests and operator approval are
    # captured. Never override it here.
    from rag.runtime.production_cutover_gate import assess_real_cutover
    with production_generation_lock(exclusive=True):
        # No time-of-check/time-of-use gap: version hashes, source state and
        # journal/pointer are checked under the SAME exclusive writer lock.
        readiness = assess_real_cutover(baseline, candidate)
        if readiness["state"] != "READY" or not readiness["safe_to_activate"]:
            raise GenerationTransitionBlocked(
                "cutover blocked: " + ",".join(readiness["blockers"])
            )
        if (root / JOURNAL_NAME).exists():
            raise GenerationTransitionBlocked("unfinished transition requires recovery")
        if _pointer_name(root) != "legacy":
            raise GenerationTransitionBlocked("source generation changed")
        payload = {
            "schema_version": 1, "state": "PREPARED",
            "previous": "legacy", "candidate": candidate,
        }
        _atomic_json(root / JOURNAL_NAME, payload)
        # Any exception after journaling leaves a durable pending record.
        # Readers fail closed until recovery under the exclusive lock.
        _atomic_json(root / POINTER_NAME, {
            "schema_version": 1, "generation": candidate,
        })
        if _pointer_name(root) != candidate:
            raise GenerationTransitionBlocked("post-switch pointer verification failed")
        _verify_target_after_pointer(
            root, candidate, readiness["verified"]["candidate"]["validation"],
        )
        (root / JOURNAL_NAME).unlink()
        return {
            "state": "POINTER_ACTIVATED_PENDING_PUBLIC_QUERY_PROOF",
            "previous": "legacy", "candidate": candidate,
        }


def rollback_pending_to_legacy(*, expected_candidate: str) -> dict[str, Any]:
    """Conservatively restore the legacy reader path after an interrupted cutover.

    No generation files are destroyed. Requires explicit candidate to prevent
    a guessed rollback target. Unknown pointer state is never overwritten.
    """
    if not _GENERATION.fullmatch(expected_candidate):
        raise GenerationTransitionBlocked("invalid expected rollback target")
    with production_generation_lock(exclusive=True):
        root = _root()
        journal = _read_journal(root)
        if not journal or journal["candidate"] != expected_candidate:
            raise GenerationTransitionBlocked("no matching pending journal")
        found = _pointer_name(root)
        if found not in ("legacy", expected_candidate):
            raise GenerationTransitionBlocked("pointer conflicts with pending journal")
        if found == expected_candidate:
            # Preserve the switched pointer for audit; do not destroy it.
            preserved = root / ("recovered-pointer-" + expected_candidate + ".json")
            if preserved.exists():
                raise GenerationTransitionBlocked("recovery pointer artifact collision")
            os.replace(root / POINTER_NAME, preserved)
        if _pointer_name(root) != "legacy":
            raise GenerationTransitionBlocked("legacy rollback pointer verification failed")
        # Only remove a journal after legacy has been selected.
        (root / JOURNAL_NAME).unlink()
        return {
            "state": "RECOVERED_LEGACY",
            "retained_generation": expected_candidate,
            "legacy_index_unmodified": True,
        }



def revert_active_to_legacy(
    *, baseline: str, expected_candidate: str,
    operator_authorization: str,
) -> dict[str, Any]:
    """Journaled rollback after a completed cutover, not just a failed one.

    Both generations survive. If interrupted after pointer removal, the
    pending journal blocks readers until rollback_pending_to_legacy reconciles.
    """
    if operator_authorization != "CODEBRIDGE_RAG_V1_ROLLBACK:" + expected_candidate:
        raise GenerationTransitionBlocked("explicit rollback approval required")
    if not _GENERATION.fullmatch(expected_candidate):
        raise GenerationTransitionBlocked("invalid rollback candidate")
    with production_generation_lock(exclusive=True):
        root = _root()
        if (root / JOURNAL_NAME).exists():
            raise GenerationTransitionBlocked("pending transition must be recovered first")
        if _pointer_name(root) != expected_candidate:
            raise GenerationTransitionBlocked("unexpected active generation")
        from rag.runtime.production_cutover_gate import _verify_versioned
        from rag.runtime.live_integrity import inspect_live_index

        saved = _verify_versioned(root, baseline, "base")
        _verify_versioned(root, expected_candidate, "delta")
        legacy = inspect_live_index()
        if (legacy["documents"] != saved["validation"]["documents"]
                or legacy["chunks"] != saved["validation"]["chunks"]):
            raise GenerationTransitionBlocked("legacy recovery source diverged")

        preserved = root / ("recovered-pointer-" + expected_candidate + ".json")
        if preserved.exists():
            raise GenerationTransitionBlocked("rollback evidence already exists")
        _atomic_json(root / JOURNAL_NAME, {
            "schema_version": 1, "state": "PREPARED",
            "previous": "legacy", "candidate": expected_candidate,
        })
        # Never delete the candidate; archive only the small pointer.
        os.replace(root / POINTER_NAME, preserved)
        if _pointer_name(root) != "legacy":
            raise GenerationTransitionBlocked("legacy recovery confirmation failed")
        (root / JOURNAL_NAME).unlink()
        return {
            "state": "RECOVERED_LEGACY",
            "retained_generation": expected_candidate,
            "legacy_index_unmodified": True,
        }
