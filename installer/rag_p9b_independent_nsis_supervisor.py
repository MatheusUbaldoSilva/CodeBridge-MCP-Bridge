"""Independent P9-B NSIS supervisor: strictly read-only preflight.

The supervisor cannot invoke NSIS, stop services, restore registry or
alter installed files. Its result deliberately NEVER authorizes cutover.
Run from an independent Python process before any future release action.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from installer.rag_p9b_three_way_backup_gate import verify_three_way
from installer.rag_p9b_external_supervisor_preflight import assess_external_supervisor
from installer.rag_p9b_crash_preimage import verify_crash_preimage
from installer.rag_p9b_poststop_verification import check_poststop


def assess_independent_release(*, installed, installer, file_snapshot,
        shell_snapshot, preimage, installer_sha, file_snapshot_sha,
        shell_snapshot_sha, preimage_sha, source_commit, appdata, desktop,
        artifact_probe=verify_three_way, process_probe=assess_external_supervisor,
        preimage_probe=verify_crash_preimage):
    base={"state":"INDEPENDENT_NSIS_SUPERVISOR_REFUSED",
          "read_only":True,"installer_executed":False,
          "installed_modified":False,"release_authorized":False,
          "rollback_executed":False,"public_handshake_verified":False}
    try:
        artifacts=artifact_probe(installer,file_snapshot,shell_snapshot,installed,
          installer_hash=installer_sha,file_snapshot_hash=file_snapshot_sha,
          shell_snapshot_hash=shell_snapshot_sha,source_commit=source_commit,
          appdata=appdata,desktop=desktop)
        if artifacts.get("verified") is not True or artifacts.get("state")!="THREE_WAY_BACKUP_OBSERVED_ONLY":
            return {**base,"reason":"THREE_WAY_ARTIFACTS_INVALID",
                    "artifact_reason":artifacts.get("reason")}
        proof=preimage_probe(preimage,preimage_sha)
        if proof.get("verified") is not True or proof.get("state")!="CRASH_PREIMAGE_VERIFIED":
            return {**base,"reason":"CRASH_PREIMAGE_INVALID"}
        state=process_probe(installed)
        if state.get("state")=="SUPERVISOR_UPDATE_BLOCKED_RUNNING":
            return {**base,"state":"INDEPENDENT_NSIS_UPDATE_BLOCKED_RUNNING",
                    "reason":"INSTALLED_STACK_STILL_RUNNING",
                    "active_roles":state.get("blockers",[]),
                    "opaque_candidates":state.get("opaque_codebridge_candidates",0),
                    "artifacts_verified":True,"preimage_verified":True}
        if state.get("state")!="SUPERVISOR_TOPOLOGY_INCOMPLETE":
            return {**base,"reason":"PROCESS_TOPOLOGY_UNVERIFIED",
                    "process_state":state.get("state")}
        # Incomplete topology is NOT evidence of all processes stopped.
        return {**base,"state":"INDEPENDENT_NSIS_POSTSTOP_PROOF_REQUIRED",
                "artifacts_verified":True,"preimage_verified":True,
                "requires_poststop_confirmation":True}
    except Exception as exc:
        return {**base,"reason":"SUPERVISOR_EVIDENCE_EXCEPTION",
                "exception_type":type(exc).__name__}


def main():
    ap=argparse.ArgumentParser()
    for name in ("installed","installer","file-snapshot","shell-snapshot",
                 "preimage","installer-sha","file-snapshot-sha",
                 "shell-snapshot-sha","preimage-sha","source-commit",
                 "appdata","desktop"):
        ap.add_argument("--"+name,required=True)
    a=vars(ap.parse_args())
    args={key.replace("-","_"):value for key,value in a.items()}
    result=assess_independent_release(**args)
    print(json.dumps(result,sort_keys=True))
    return 2

if __name__=="__main__":
    raise SystemExit(main())
