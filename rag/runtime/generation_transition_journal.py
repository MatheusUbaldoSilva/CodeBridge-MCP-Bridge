"""Durable, test-only generation transition journal and conservative recovery.

Never guesses recovery targets; never removes generation directories.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from rag.runtime.generation_activation import PUBLICATION_LOCK_NAME
from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_recovery_candidate import verify_recovery_candidate

JOURNAL = "transition-pending.json"


class TransitionRecoveryError(RuntimeError):
    pass


def _test_root(state_root):
    root = Path(state_root).resolve()
    if root.name.casefold() != "codebridge-rag-generation-test":
        raise TransitionRecoveryError("test root required")
    return root


def _atomic_json(path, payload):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".transition.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_transition(test_root, previous, candidate):
    root = _test_root(test_root)
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        if (root / JOURNAL).exists():
            raise TransitionRecoveryError("pending transition already exists")
        active = resolve_generation(root)
        if active is None or active.generation != previous or previous == candidate:
            raise TransitionRecoveryError("unexpected active generation")
        verify_recovery_candidate(root, previous)
        verify_recovery_candidate(root, candidate)
        _atomic_json(root / JOURNAL, {
            "schema_version": 1, "previous": previous, "candidate": candidate,
        })


def inspect_pending_transition(test_root):
    root = _test_root(test_root)
    pending = root / JOURNAL
    if not pending.is_file():
        return {"state": "NO_PENDING_TRANSITION"}
    try:
        payload = json.loads(pending.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or payload.get("schema_version") != 1
                or not isinstance(payload.get("previous"), str)
                or not isinstance(payload.get("candidate"), str)
                or payload["previous"] == payload["candidate"]):
            raise ValueError("invalid journal")
    except (ValueError, OSError) as exc:
        return {"state": "BLOCKED_MANUAL_RECOVERY", "reason": str(exc)}
    return {"state": "PENDING_TRANSITION", **payload}


def recover_pending_transition(test_root):
    root = _test_root(test_root)
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        info = inspect_pending_transition(root)
        if info["state"] == "NO_PENDING_TRANSITION":
            return info
        if info["state"] != "PENDING_TRANSITION":
            raise TransitionRecoveryError("journal invalid; manual inspection required")
        previous, candidate = info["previous"], info["candidate"]
        try:
            active = resolve_generation(root)
            verify_recovery_candidate(root, previous)
            verify_recovery_candidate(root, candidate)
        except Exception as exc:
            raise TransitionRecoveryError("generation validation failed; no changes made") from exc
        if active is None or active.generation not in (previous, candidate):
            raise TransitionRecoveryError("active generation conflicts with journal")
        if active.generation == candidate:
            _atomic_json(root / "active-generation.json", {
                "schema_version": 1, "generation": previous,
            })
            restored = resolve_generation(root)
            if restored is None or restored.generation != previous:
                raise TransitionRecoveryError("rollback verification failed")
        # Keep journal for investigation if verification fails.
        (root / JOURNAL).unlink()
        return {"state": "RECOVERED_PREVIOUS", "generation": previous}
