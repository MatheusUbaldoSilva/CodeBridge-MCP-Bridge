"""Journaled test-only publication; no production integration or deletion."""
from __future__ import annotations
from pathlib import Path
from rag.runtime.generation_activation import PUBLICATION_LOCK_NAME
from rag.runtime.generation_process_lock import generation_lock
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_recovery_candidate import verify_recovery_candidate
from rag.runtime.generation_transition_journal import (
    JOURNAL, _atomic_json, _test_root, inspect_pending_transition,
    prepare_transition, TransitionRecoveryError,
)


def publish_test_generation(root, previous, candidate, *, fail_before_switch=False,
                            fail_after_switch=False):
    root = _test_root(root)
    # Prepare under its own publication lock and leave durable intent on disk.
    prepare_transition(root, previous, candidate)
    with generation_lock(root, PUBLICATION_LOCK_NAME, exclusive=True):
        info = inspect_pending_transition(root)
        if (info.get("state") != "PENDING_TRANSITION" or
                info.get("previous") != previous or info.get("candidate") != candidate):
            raise TransitionRecoveryError("journal mismatch; recovery required")
        active = resolve_generation(root)
        if active is None or active.generation != previous:
            raise TransitionRecoveryError("active changed; recovery required")
        verify_recovery_candidate(root, previous)
        verify_recovery_candidate(root, candidate)
        if fail_before_switch:
            raise TransitionRecoveryError("injected interruption before switch")
        _atomic_json(root / "active-generation.json",
                     {"schema_version": 1, "generation": candidate})
        if fail_after_switch:
            raise TransitionRecoveryError("injected interruption after switch")
        selected = resolve_generation(root)
        if selected is None or selected.generation != candidate:
            raise TransitionRecoveryError("post-switch verification failed")
        verify_recovery_candidate(root, candidate)
        (root / JOURNAL).unlink()
        return {"state": "PUBLISHED_TEST_ONLY", "active": candidate, "previous": previous}
