"""Read-only same-machine NSIS upgrade gate; no shutdown/install actions."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from installer.rag_p9b_shell_postverify import verify_restored_shell
from installer.rag_p9b_crash_preimage import verify_crash_preimage
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_transaction_identity import verify_identity
from installer.rag_p9b_installer_rollback_scope import (
    verify_installer_rollback_snapshot,inspect_installer_snapshot_baseline)
from installer.rag_p9b_external_supervisor_preflight import assess_external_supervisor

def assess(*,identity,identity_sha,installed,worktree,appdata=None,desktop=None,
           process_probe=assess_external_supervisor,shell_probe=None,
           preimage_probe=verify_crash_preimage):
    refused={"state":"CURRENT_MACHINE_CUTOVER_REFUSED","authorized":False,
             "read_only":True,"production_modified":False}
    try:
        manifest_path=Path(identity)
        proof=verify_identity(manifest_path,identity_sha)
        if proof.get("verified") is not True:
            return {**refused,"reason":"TRANSACTION_IDENTITY_INVALID"}
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if Path(manifest["installed"]).resolve()!=Path(installed).resolve():
            return {**refused,"reason":"INSTALLED_PATH_MISMATCH"}
        file_zip=Path(manifest["artifacts"]["file_snapshot"]["path"])
        snapshot=verify_installer_rollback_snapshot(file_zip,installed)
        if snapshot.get("verified") is not True or snapshot.get("targets")!=258 or snapshot.get("existing_files")!=236:
            return {**refused,"reason":"FILE_SCOPE_NOT_VERIFIED"}
        baseline=inspect_installer_snapshot_baseline(file_zip,installed)
        if baseline.get("matches") is not True:
            return {**refused,"reason":"LIVE_BASELINE_HAS_DRIFT"}
        preimage=manifest["artifacts"]["crash_preimage"]
        preproof=preimage_probe(preimage["path"],preimage["sha256"])
        if preproof.get("verified") is not True:
            return {**refused,"reason":"CRASH_PREIMAGE_INVALID"}
        if shell_probe is None:
            if appdata is None or desktop is None:
                return {**refused,"reason":"SHELL_LOCATIONS_REQUIRED"}
            registry=ScopedHKCU()
            shell_probe=lambda path:verify_restored_shell(
                path,appdata=appdata,desktop=desktop,
                registry_values=lambda key,names:registry.read_key(key))
        shell_path=manifest["artifacts"]["shell_snapshot"]["path"]
        live_shell=shell_probe(shell_path)
        if live_shell.get("verified") is not True:
            return {**refused,"reason":"LIVE_SHELL_HAS_DRIFT"}
        topology=process_probe(installed)
        # Running and ambiguous topologies are both a hard veto.
        if topology.get("state")!="SUPERVISOR_TOPOLOGY_INCOMPLETE":
            return {**refused,"reason":"PROCESSES_NOT_EXTERNALLY_STOPPED",
                    "process_state":topology.get("state")}
        # Topology incomplete NEVER means shutdown is proven.
        source_commit=manifest["source_commit"]
        source_marker=Path(worktree)/"installer"/"CodeBridge.nsi"
        if not source_marker.is_file():
            return {**refused,"reason":"INSTALLER_SOURCE_NOT_FOUND"}
        return {**refused,"state":"CURRENT_MACHINE_EXTERNAL_STOP_PROOF_REQUIRED",
                "reason":"INDEPENDENT_POSTSTOP_AND_PRODUCTION_RECOVERY_UNVERIFIED",
                "source_commit":source_commit,"snapshot_existing":236,
                "snapshot_new_targets":22}
    except (OSError,KeyError,TypeError,ValueError):
        return {**refused,"reason":"PREFLIGHT_EXCEPTION"}
