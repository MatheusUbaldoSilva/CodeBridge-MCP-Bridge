"""Fail-closed P9-B installer cutover readiness review.

Evaluates evidence for a future official installer update; does not run the
installer, stop CodeBridge or grant deployment permission.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from installer.rag_p9b_installer_rollback_scope import (
    inspect_installer_snapshot_baseline, verify_installer_rollback_snapshot,
)


def assess_p9b_official_update(
    *, installer: Path, installed: Path, snapshot: Path,
    expected_installer_sha256: str,
    mcp_process_running: bool | None,
    codebridge_gui_running: bool | None,
    independent_recovery_online: bool,
    scratch_restore_proven: bool,
    public_generation: str,
    journal_present: bool,
) -> dict:
    blockers = []
    def deny(code: str):
        if code not in blockers:
            blockers.append(code)

    installer = Path(installer)
    if (not installer.is_file() or installer.is_symlink()
            or len(expected_installer_sha256) != 64
            or hashlib.sha256(installer.read_bytes()).hexdigest()
            != expected_installer_sha256.lower()):
        deny("CLEAN_INSTALLER_HASH_NOT_VERIFIED")
    proof = verify_installer_rollback_snapshot(snapshot, installed)
    if (not proof["verified"]
            or proof.get("installer_sha256") != expected_installer_sha256.lower()):
        deny("FULL_INSTALLER_ROLLBACK_SNAPSHOT_UNVERIFIED")
    else:
        baseline = inspect_installer_snapshot_baseline(snapshot, installed)
        if not baseline["matches"]:
            deny("INSTALLED_SOURCE_CHANGED_SINCE_BACKUP")
    if scratch_restore_proven is not True:
        deny("INDEPENDENT_RESTORE_NOT_REHEARSED")
    if independent_recovery_online is not True:
        deny("INDEPENDENT_RECOVERY_CHANNEL_NOT_VERIFIED")
    if mcp_process_running is not False:
        deny("ACTIVE_MCP_MUST_SHUT_DOWN")
    if codebridge_gui_running is not False:
        deny("ACTIVE_CODEBRIDGE_GUI_MUST_SHUT_DOWN")
    if public_generation != "v1_delta_1ae1d01ea84f4e":
        deny("PUBLIC_RAG_GENERATION_CHANGED")
    if journal_present is not False:
        deny("PUBLIC_GENERATION_TRANSITION_PENDING")
    return {
        "state": ("MAINTENANCE_PREFLIGHT_OBSERVED_ONLY" if not blockers
                  else "OFFICIAL_UPDATE_BLOCKED"),
        "blockers": blockers, "installer_executed": False,
        "mcp_restarted": False, "installed_modified": False,
        "public_index_updated": False, "queue_initialized": False,
        "operator_execution_authorized": False,
        "requires_fresh_recheck_at_apply": True,
    }
