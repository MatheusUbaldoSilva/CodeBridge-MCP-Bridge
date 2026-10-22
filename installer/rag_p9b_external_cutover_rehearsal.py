"""One-shot external stop/restart rehearsal; no installer execution.

MUST be started through an independent supervisory connection.
An exact live digest and two execution flags are required. Failure
to stop triggers GUI recovery when the original GUI has exited.
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path

from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan
from installer.rag_p9b_shutdown_executor import execute_shutdown
from installer.rag_p9b_external_recovery import recover_gui
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_poststart_health import check_local_poststart


def rehearse_cutover(installed:Path, *, expected_digest:str,
                     external_channel=False, execute=False,
                     plan=None, stop=None, recover=None, verify=None,
                     local_health=None):
    base={"state":"CUTOVER_REHEARSAL_REFUSED",
          "installer_executed":False,"public_index_modified":False,
          "queue_initialized":False}
    if external_channel is not True or execute is not True:
        return {**base,"reason":"EXTERNAL_EXECUTION_REQUIRED"}
    plan=plan or make_shutdown_plan
    stop=stop or execute_shutdown
    recover=recover or recover_gui
    verify=verify or check_poststop
    local_health=local_health or check_local_poststart
    snapshot=plan(installed)
    if snapshot.get("state")!="SHUTDOWN_PLAN_ONLY" or snapshot.get("identity_digest")!=expected_digest:
        return {**base,"reason":"IDENTITY_PLAN_CHANGED"}
    stopped=stop(installed,expected_digest=expected_digest,
                 execute=True,independent=True)
    if not stopped.get("processes_stopped"):
        if stopped.get("state")=="PARTIAL_SHUTDOWN":
            try:
                restored=recover(installed)
            except Exception:
                restored={"state":"RECOVERY_EXCEPTION"}
            return {**base,"state":"CUTOVER_PARTIAL_SHUTDOWN_RECOVERY_ATTEMPTED",
                    "stop_reason":stopped.get("reason"),
                    "recovery_state":restored.get("state"),
                    "mcp_handshake_verified":False}
        return {**base,"state":"CUTOVER_STOP_FAILED",
                "stop_state":stopped.get("state"),
                "reason":stopped.get("reason")}
    try:
        proof=verify(installed)
    except Exception:
        proof={"state":"POSTSTOP_CHECK_EXCEPTION",
               "observed_stopped":False,"reason":"POSTSTOP_CHECK_EXCEPTION"}
    try:
        recovery=recover(installed)
    except Exception:
        recovery={"state":"RECOVERY_EXCEPTION"}
    if recovery.get("state")!="GUI_PROCESS_RECOVERED":
        return {**base,"state":"CUTOVER_RECOVERY_UNVERIFIED",
                "poststop":proof.get("state"),
                "recovery":recovery.get("state")}
    if not proof.get("observed_stopped"):
        return {**base,"state":"CUTOVER_POSTSTOP_UNVERIFIED",
                "recovery":recovery.get("state"),
                "reason":proof.get("reason")}
    try:
        health=local_health(installed)
    except Exception:
        health={"state":"POSTSTART_PROBE_EXCEPTION","verified":False}
    if not health.get("verified"):
        return {**base,"state":"CUTOVER_MCP_LOCAL_UNVERIFIED",
                "gui_recovered":True,"health_state":health.get("state"),
                "mcp_handshake_verified":False}
    return {**base,"state":"CUTOVER_LOCAL_STACK_RECOVERED",
            "gui_recovered":True,"mcp_local_verified":True,
            "mcp_handshake_verified":False,
            "requires_public_handshake":True}
