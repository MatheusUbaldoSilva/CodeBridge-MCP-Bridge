"""Detached shutdown/restart controller, laboratory-injectable and fail-closed.

No NSIS launch or automatic mutation. This orchestration only becomes usable
when a separately audited external host supplies identity proof, journal and
workers; the default call always refuses.
"""
from __future__ import annotations

from pathlib import Path

from installer.rag_p9b_detached_supervisor_gate import assess_detached_supervisor
from installer.rag_p9b_shutdown_executor import execute_shutdown
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_external_recovery import recover_gui
from installer.rag_p9b_same_machine_external_probe import inspect_external_runtime


def run_detached_shutdown_recovery(*, installed, identity_manifest,
                                   identity_sha256, source_commit,
                                   expected_process_digest, journal=None,
                                   external=False, execute=False,
                                   external_interpreter=None,
                                   external_psutil_origin=None,
                                   external_staged_lib=None,
                                   runtime_probe=inspect_external_runtime,
                                   proof=assess_detached_supervisor,
                                   shutdown=execute_shutdown,
                                   poststop=check_poststop,
                                   restart=recover_gui):
    base={"state":"DETACHED_LIFECYCLE_REFUSED","verified":False,
          "installer_executed":False,"installer_authorized":False,
          "installed_modified":False}
    if not (external is True and execute is True and callable(journal)
            and isinstance(expected_process_digest,str)
            and len(expected_process_digest)==64):
        return {**base,"reason":"INDEPENDENT_CONTROLLER_REQUIRED"}
    try:
        runtime=runtime_probe(installed=installed,
            interpreter=external_interpreter,
            psutil_origin=external_psutil_origin,
            staged_lib=external_staged_lib)
        if (not isinstance(runtime,dict)
                or runtime.get("state")!="EXTERNAL_RUNTIME_PATHS_VERIFIED"
                or runtime.get("verified") is not True):
            return {**base,"reason":"EXTERNAL_RUNTIME_PATHS_REQUIRED"}
        report=proof(installed=installed,identity_manifest=identity_manifest,
            identity_sha256=identity_sha256,source_commit=source_commit,
            external_runtime=True)
        if (not isinstance(report,dict)
                or report.get("state")!="DETACHED_SUPERVISOR_SHUTDOWN_PENDING"
                or report.get("artifacts_verified") is not True
                or report.get("shutdown_identity_digest")!=expected_process_digest
                or report.get("authorized") is not False):
            return {**base,"reason":"SHUTDOWN_PLAN_OR_IDENTITY_CHANGED"}
        journal("SHELL_DETACHED_LIFECYCLE_ARMED",{})
        stop=shutdown(installed,expected_digest=expected_process_digest,
                      independent=True,execute=True)
        if (not isinstance(stop,dict)
                or stop.get("state")!="SHUTDOWN_SIGNALS_COMPLETED"
                or stop.get("processes_stopped") is not True):
            journal("SHELL_DETACHED_SHUTDOWN_UNVERIFIED",{})
            return {**base,"state":"DETACHED_LIFECYCLE_REVIEW_REQUIRED",
                    "reason":"SHUTDOWN_FAILED",
                    "restart_review_required":True}
        journal("SHELL_DETACHED_SHUTDOWN_SIGNALED",{})
        check=poststop(Path(installed))
        if (not isinstance(check,dict)
                or check.get("state")!="POSTSTOP_OBSERVED_ONLY"
                or check.get("observed_stopped") is not True):
            journal("SHELL_DETACHED_POSTSTOP_UNVERIFIED",{})
            return {**base,"state":"DETACHED_LIFECYCLE_REVIEW_REQUIRED",
                    "reason":"POSTSTOP_NOT_PROVEN",
                    "restart_review_required":True}
        journal("SHELL_DETACHED_POSTSTOP_VERIFIED",{"postverified":True})
        restored=restart(Path(installed))
        if (not isinstance(restored,dict)
                or restored.get("state")!="GUI_PROCESS_RECOVERED"
                or restored.get("launched") is not True):
            journal("SHELL_DETACHED_RESTART_UNVERIFIED",{})
            return {**base,"state":"DETACHED_LIFECYCLE_REVIEW_REQUIRED",
                    "reason":"RESTART_NOT_CONFIRMED"}
        journal("SHELL_DETACHED_GUI_RESTARTED",{})
        return {**base,"state":"DETACHED_GUI_RESTARTED_HANDSHAKE_PENDING",
                "requires_public_mcp_handshake":True,
                "requires_rag_queue_validation":True}
    except Exception as exc:
        try:
            journal("SHELL_DETACHED_LIFECYCLE_EXCEPTION",
                    {"type":type(exc).__name__})
        except Exception:
            pass
        return {**base,"state":"DETACHED_LIFECYCLE_REVIEW_REQUIRED",
                "reason":"LIFECYCLE_WORKER_EXCEPTION"}
