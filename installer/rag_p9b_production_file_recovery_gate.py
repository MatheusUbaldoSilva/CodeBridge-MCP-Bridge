"""Read-only external file rollback gate. Never mutates CodeBridge installation.

The gate assembles evidence; it does NOT confer installation or deletion
authority. A separate audited executor must independently check every gate.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from installer.rag_p9b_installer_rollback_scope import verify_installer_rollback_snapshot
from installer.rag_p9b_crash_preimage import verify_crash_preimage
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_rollback_journal import read_journal, RollbackJournal
from installer.rag_p9b_rollback_new_targets import inspect_new_targets

_INCOMPLETE = frozenset({
    "SHELL_NSIS_INTERRUPTED", "SHELL_NSIS_FULL_SCOPE_INTERRUPTED",
    "SHELL_PRODUCTION_FILE_RESTORE_ARMED",
    "SHELL_PRODUCTION_FILE_BEFORE_REPLACE",
    "SHELL_PRODUCTION_FILE_BEFORE_UNLINK",
    "SHELL_PRODUCTION_FILE_RESTORE_FAILED",
    "SHELL_PRODUCTION_FILE_POSTVERIFY_FAILED",
})


def assess_file_recovery(*, installed, snapshot, snapshot_sha256, preimage,
                         preimage_sha256, journal_path, expected_new_hashes,
                         independent=False,
                         snapshot_probe=verify_installer_rollback_snapshot,
                         preimage_probe=verify_crash_preimage,
                         poststop_probe=check_poststop,
                         journal_probe=read_journal,
                         journal_resume_probe=RollbackJournal.resume,
                         new_targets_probe=inspect_new_targets):
    denied = {"state": "PRODUCTION_FILE_RECOVERY_REFUSED",
              "verified": False, "read_only": True,
              "delete_authorized": False, "installer_executed": False,
              "installed_modified": False}
    if independent is not True:
        return {**denied, "reason": "INDEPENDENT_RUNTIME_REQUIRED"}
    try:
        root = Path(installed).resolve()
        backup = Path(snapshot).absolute()
        if (not backup.is_file() or backup.is_symlink()
                or backup.is_relative_to(root)
                or any(p.is_symlink() for p in backup.parents)):
            return {**denied, "reason": "SNAPSHOT_LOCATION_UNTRUSTED"}
        digest = str(snapshot_sha256).lower()
        if (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
                or hashlib.sha256(backup.read_bytes()).hexdigest() != digest):
            return {**denied, "reason": "SNAPSHOT_SHA256_INVALID"}
        snapshot_state = snapshot_probe(backup, root)
        if (not isinstance(snapshot_state, dict)
                or snapshot_state.get("verified") is not True
                or snapshot_state.get("state") != "INSTALLER_ROLLBACK_SNAPSHOT_VERIFIED"):
            return {**denied, "reason": "SNAPSHOT_MANIFEST_UNVERIFIED"}
        preimage_state = preimage_probe(preimage, preimage_sha256)
        if (not isinstance(preimage_state, dict)
                or preimage_state.get("verified") is not True
                or preimage_state.get("state") != "CRASH_PREIMAGE_VERIFIED"):
            return {**denied, "reason": "DURABLE_PREIMAGE_UNVERIFIED"}
        journal_state = journal_probe(journal_path)
        if (not isinstance(journal_state, dict)
                or journal_state.get("state") != "JOURNAL_OBSERVED_ONLY"
                or journal_state.get("last_state") not in _INCOMPLETE
                or journal_state.get("count", 0) < 1):
            return {**denied, "reason": "INTERRUPTED_JOURNAL_UNVERIFIED"}
        # Re-read the full journal and validate its starting state, event
        # names, sequence and absence of a prior terminal success.
        journal_resume_probe(journal_path)
        stop_state = poststop_probe(root)
        if (not isinstance(stop_state, dict)
                or stop_state.get("state") != "POSTSTOP_OBSERVED_ONLY"
                or stop_state.get("observed_stopped") is not True):
            return {**denied, "reason": "STOPPED_PROCESS_PROOF_MISSING"}
        new_state = new_targets_probe(
            backup, root, expected_new_hashes=expected_new_hashes)
        if (not isinstance(new_state, dict)
                or new_state.get("state") != "NEW_TARGETS_CONTENT_VERIFIED"
                or new_state.get("ownership_evidence_verified") is not True
                or new_state.get("delete_authorized") is not False):
            return {**denied, "reason": "NEW_TARGET_OWNERSHIP_UNVERIFIED"}
        return {**denied, "state": "PRODUCTION_FILE_ROLLBACK_GATES_OBSERVED_ONLY",
                "snapshot_verified": True, "preimage_verified": True,
                "poststop_verified": True, "journal_verified": True,
                "new_targets_verified": True,
                "requires_detached_mutation_executor": True}
    except (OSError, ValueError, TypeError, KeyError):
        return {**denied, "reason": "FILE_RECOVERY_PREFLIGHT_EXCEPTION"}
