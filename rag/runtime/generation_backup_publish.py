"""Backup-gated journal publication, restricted to isolated generation test roots."""
from __future__ import annotations
from rag.runtime.generation_verified_backup import (
    backup_generation, verify_generation_backup)
from rag.runtime.generation_journaled_publish import publish_test_generation
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_transition_journal import inspect_pending_transition


def publish_with_verified_backup(root, previous, candidate, backup_name,
                                 *, fail_after_backup=False, fail_after_switch=False):
    # Never generate a backup during unresolved recovery or from a stale pointer.
    if inspect_pending_transition(root)["state"] != "NO_PENDING_TRANSITION":
        raise RuntimeError("pending transition requires recovery")
    selected = resolve_generation(root)
    if selected is None or selected.generation != previous:
        raise RuntimeError("active generation changed")
    backup = backup_generation(root, previous, backup_name)
    verification = verify_generation_backup(root, backup_name)
    if verification != backup["report"]:
        raise RuntimeError("backup verification mismatch")
    if fail_after_backup:
        raise RuntimeError("injected interruption after verified backup")
    publication = publish_test_generation(
        root, previous, candidate, fail_after_switch=fail_after_switch)
    return {"state": "BACKUP_GATED_TEST_PUBLICATION",
            "backup": backup["path"], "published": publication}
