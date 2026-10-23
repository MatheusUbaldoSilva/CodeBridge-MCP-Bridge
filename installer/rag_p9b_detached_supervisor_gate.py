"""External same-machine supervisor gate; read-only by construction.

This is a detached preflight; never turns a green probe into permission
to close the running MCP, execute NSIS, mutate HKCU or apply rollback.
"""
from __future__ import annotations

from pathlib import Path

from installer.rag_p9b_detached_combined_identity_gate import assess_detached_identity
from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan
from installer.rag_p9b_poststop_verification import check_poststop


def assess_detached_supervisor(*, installed, identity_manifest,
                              identity_sha256, source_commit,
                              external_runtime=False,
                              identity_probe=assess_detached_identity,
                              shutdown_probe=make_shutdown_plan,
                              stopped_probe=check_poststop):
    base={"state":"DETACHED_SUPERVISOR_REFUSED",
          "authorized":False,"read_only":True,
          "installer_executed":False,"installed_modified":False,
          "shutdown_signals_sent":False}
    if external_runtime is not True:
        return {**base,"reason":"EXTERNAL_RUNTIME_REQUIRED"}
    try:
        proof=identity_probe(manifest=identity_manifest,
            manifest_sha256=identity_sha256,installed=installed,
            expected_source_commit=source_commit)
        if (not isinstance(proof,dict)
                or proof.get("state")!="DETACHED_IDENTITY_OBSERVED_ONLY"
                or proof.get("identity_verified") is not True
                or proof.get("artifacts_checked")!=4):
            return {**base,"reason":"BOUND_IDENTITY_INVALID"}
        shutdown=shutdown_probe(Path(installed))
        if not isinstance(shutdown,dict):
            return {**base,"reason":"SHUTDOWN_PLAN_INVALID"}
        if shutdown.get("state")=="SHUTDOWN_PLAN_ONLY":
            return {**base,"state":"DETACHED_SUPERVISOR_SHUTDOWN_PENDING",
                    "reason":"INDEPENDENT_SHUTDOWN_NOT_EXECUTED",
                    "shutdown_identity_digest":shutdown.get("identity_digest"),
                    "artifacts_verified":True}
        stopped=stopped_probe(Path(installed))
        if (not isinstance(stopped,dict)
                or stopped.get("state")!="POSTSTOP_OBSERVED_ONLY"
                or stopped.get("observed_stopped") is not True):
            return {**base,"reason":"INDEPENDENT_STOPPED_PROOF_MISSING"}
        return {**base,"state":"DETACHED_SUPERVISOR_POSTSTOP_OBSERVED",
                "artifacts_verified":True,
                "processes_stopped_observed":True,
                "reason":"MUTATING_RECOVERY_EXECUTOR_NOT_YET_CERTIFIED"}
    except (OSError,ValueError,TypeError,KeyError):
        return {**base,"reason":"DETACHED_SUPERVISOR_PROBE_ERROR"}
