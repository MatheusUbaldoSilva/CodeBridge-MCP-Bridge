"""Independent read-only proof after a planned CodeBridge shutdown.

A green result is only an observed prerequisite, not permission to
execute NSIS. The external operator must also verify the rollback
snapshot and re-evaluate the official process guard at apply time.
"""
from __future__ import annotations

import socket
from pathlib import Path

if not __package__:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from installer.p9b_update_process_guard import inspect_update_processes
from installer.rag_p9b_external_supervisor_preflight import (
    assess_external_supervisor,
)


def check_poststop(
    installed: Path, *, process_records=None, official_processes=None,
    port_probe=None,
) -> dict:
    result = {
        "state": "POSTSTOP_UNVERIFIED", "observed_stopped": False,
        "installer_launch_authorized": False, "installer_executed": False,
        "files_modified": False, "inspection_only": True,
    }
    root = Path(installed).resolve()
    if process_records is None:
        try:
            import psutil
            process_records = [p.info for p in psutil.process_iter(
                attrs=["pid", "ppid", "name", "cmdline", "create_time", "exe"]
            )]
        except Exception:
            return {**result, "reason": "PROCESS_ENUMERATION_UNAVAILABLE"}
    records = list(process_records)
    inspection = assess_external_supervisor(root, records=records)
    if inspection["state"] not in {
        "SUPERVISOR_TOPOLOGY_INCOMPLETE",
        "SUPERVISOR_PREFLIGHT_UNVERIFIED",
        "SUPERVISOR_UPDATE_BLOCKED_RUNNING",
    }:
        return {**result, "reason": "TOPOLOGY_UNRELIABLE"}
    if inspection.get("processes"):
        return {**result, "reason": "CODEBRIDGE_PROCESSES_STILL_RUNNING",
                "processes": inspection["processes"]}
    if inspection.get("opaque_codebridge_candidates", 0):
        return {**result, "reason": "OPAQUE_PROCESS_IDENTITY"}
    guard = inspect_update_processes(root, process_iter=official_processes)
    if guard.get("state") != "NO_RUNNING_CODEBRIDGE":
        return {**result, "reason": "OFFICIAL_GUARD_NOT_CLEAR",
                "guard_state": guard.get("state")}
    if port_probe is None:
        def port_probe(host, port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                return s.connect_ex((host, port)) == 0
    try:
        if any(port_probe("127.0.0.1", p) for p in (8765, 8767)):
            return {**result, "reason": "MCP_LISTENER_STILL_ONLINE"}
    except (OSError, ValueError, TypeError):
        return {**result, "reason": "PORT_STATE_UNVERIFIED"}
    return {**result, "state": "POSTSTOP_OBSERVED_ONLY",
            "observed_stopped": True,
            "requires_recheck_before_nsis": True,
            "rollback_reverify_required": True}


def main(argv=None):
    import argparse
    import json
    ap=argparse.ArgumentParser()
    ap.add_argument("--install-root",required=True,type=Path)
    args=ap.parse_args(argv)
    r=check_poststop(args.install_root)
    print(json.dumps(r,sort_keys=True))
    # Never interpret a poststop observation as NSIS approval.
    return 2


if __name__=="__main__":
    raise SystemExit(main())
