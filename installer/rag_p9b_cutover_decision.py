"""One read-only P9-B update decision from independently collected gates.

Never launches NSIS and cannot override its built-in process guard.
"""
from __future__ import annotations

from installer.rag_p9b_artifact_pair_gate import assess_artifact_pair
from installer.p9b_update_process_guard import inspect_update_processes


def decide_cutover(*, installer, snapshot, installed, installer_sha,
                   snapshot_sha, source_commit, generation,
                   independent_channel_ready=False,
                   scratch_restore_proven=False,
                   pair_check=assess_artifact_pair,
                   process_check=inspect_update_processes):
    base=dict(state="P9B_CUTOVER_REFUSED",
              installer_executed=False,
              operator_execution_authorized=False,
              installed_modified=False)
    pair=pair_check(installer,snapshot,installed,
                    expected_installer_sha256=installer_sha,
                    expected_snapshot_sha256=snapshot_sha,
                    expected_source_commit=source_commit)
    if pair.get("paired") is not True:
        return {**base,"reason":"INSTALLER_BACKUP_PAIR_UNVERIFIED",
                "pair_reason":pair.get("reason")}
    if generation!="v1_delta_1ae1d01ea84f4e":
        return {**base,"reason":"RAG_GENERATION_CHANGED"}
    if not independent_channel_ready or not scratch_restore_proven:
        return {**base,"reason":"RECOVERY_PREREQUISITE_MISSING"}
    guard=process_check(installed)
    if guard.get("state")!="NO_RUNNING_CODEBRIDGE":
        return {**base,"reason":"NSIS_PROCESS_GUARD_BLOCKED",
                "process_state":guard.get("state"),
                "blockers":guard.get("blockers")}
    # Even a clean observation is not permission to mutate;
    # the NSIS gate is re-run at execution time.
    return {**base,"state":"P9B_PREFLIGHT_OBSERVED_ONLY",
            "requires_fresh_nsis_recheck":True,
            "artifact_pair_verified":True}
