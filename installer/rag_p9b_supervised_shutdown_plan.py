"""Create a read-only, process-identity-scoped P9-B shutdown proposal.

This module never signals any process, runs the installer, or claims an
installation can proceed. An executor must perform separate fresh checks.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from installer.rag_p9b_external_supervisor_preflight import assess_external_supervisor


ROLES = ("GUI", "MCP", "ADAPTER", "TUNNEL")


def make_shutdown_plan(installed: Path, *, records=None) -> dict:
    review = assess_external_supervisor(installed, records=records)
    base = {
        "state": "SHUTDOWN_PLAN_REFUSED",
        "execute": False,
        "signals_sent": False,
        "installer_executed": False,
        "safe_to_apply_installer": False,
        "review_state": review.get("state"),
    }
    if review.get("state") != "SUPERVISOR_UPDATE_BLOCKED_RUNNING":
        return {**base, "reason": "TOPOLOGY_UNVERIFIED"}
    processes = review.get("processes", [])
    roles = [item["component"] for item in processes]
    if sorted(roles) != sorted(ROLES):
        return {**base, "reason": "UNEXPECTED_PROCESS_MULTIPLICITY",
                "observed_roles": sorted(roles)}
    if review.get("parent_age_conflicts"):
        return {**base, "reason": "PROCESS_AGE_CONFLICT"}
    mcp=next(x for x in processes if x["component"]=="MCP")
    gui=next(x for x in processes if x["component"]=="GUI")
    # On current Windows versions MCP may be a direct child of the GUI,
    # rather than an adopted/orphan process. Both are valid only if the
    # process is otherwise uniquely identified and birth ordering agrees.
    mcp_parent=next(x["parent_pid"] for x in review["processes"]
                    if x["component"]=="MCP")
    adopted=review.get("mcp_parent_absent")==[mcp["pid"]]
    gui_child=mcp_parent==gui["pid"] and mcp["create_time"]>=gui["create_time"]
    if not (adopted or gui_child):
        return {**base, "reason": "UNEXPECTED_MCP_ANCESTRY"}
    scope = sorted(
        ({"component": x["component"],
          "pid": x["pid"],
          "create_time": x["create_time"]} for x in processes),
        key=lambda x: x["component"],
    )
    digest = sha256(json.dumps(scope, sort_keys=True,
                               separators=(",", ":")).encode()).hexdigest()
    return {**base, "state": "SHUTDOWN_PLAN_ONLY",
            "reason": "EXTERNAL_EXECUTOR_AND_FRESH_IDENTITY_REQUIRED",
            "identity_digest": digest,
            "processes": scope,
            "opaque_processes": review.get("opaque_processes", 0),
            "requires": [
                "INDEPENDENT_RECOVERY_CHANNEL",
                "GUI_GRACEFUL_CLOSE",
                "MCP_TARGETED_GRACEFUL_CLOSE",
                "PROCESS_GUARD_RECHECK",
                "POST_RESTART_HANDSHAKE",
            ]}


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--install-root",type=Path,required=True)
    args=p.parse_args(argv)
    report=make_shutdown_plan(args.install_root)
    print(json.dumps(report,sort_keys=True))
    # A planned shutdown must NEVER be a green light for NSIS.
    return 2


if __name__=="__main__":
    raise SystemExit(main())
