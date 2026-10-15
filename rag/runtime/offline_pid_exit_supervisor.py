"""Read-only laboratory proof that specified Windows process identities disappeared.

It never stops processes, never authorizes copying, and treats PID reuse or
unreadable inventories as blockers. A clean result is NOT global quiescence.
"""
from __future__ import annotations

import time
from rag.runtime.offline_pid_identity_audit import inspect_process_identities


def _identity(row):
    if not isinstance(row, dict):
        raise ValueError("invalid identity")
    pid = row.get("pid")
    born = row.get("created_at")
    executable = row.get("executable_fingerprint")
    if (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or
            not isinstance(born, str) or not born or
            not isinstance(executable, str) or len(executable) != 64 or
            any(ch not in "0123456789abcdef" for ch in executable)):
        raise ValueError("incomplete process identity")
    return (pid, born, executable)


def supervise_expected_exits(expected, *, observer=inspect_process_identities,
                             samples=3, pause_seconds=0.05, sleeper=time.sleep):
    """Observe snapshots without killing processes or claiming shutdown success."""
    report = {"state": "BLOCKED", "samples_completed": 0,
              "observed_exit_pids": [], "copy_authorized": False,
              "production_quiescence_proven": False,
              "all_handles_closed": False, "issues": []}
    try:
        if (not isinstance(expected, list) or not expected or
                not isinstance(samples, int) or isinstance(samples, bool) or
                not 2 <= samples <= 20 or
                not isinstance(pause_seconds, (int, float)) or
                isinstance(pause_seconds, bool) or not 0 <= pause_seconds <= 2):
            raise ValueError("invalid supervisor arguments")
        baselines = {_identity(row) for row in expected}
        if len(baselines) != len(expected):
            raise ValueError("duplicate baseline identity")
        expected_by_pid = {x[0]: x for x in baselines}
        if len(expected_by_pid) != len(baselines):
            raise ValueError("duplicate baseline PID")
        consecutive_absence = 0
        for index in range(samples):
            snapshot = observer()
            if (not isinstance(snapshot, dict) or
                    snapshot.get("identity_inventory_ok") is not True or
                    snapshot.get("unverified_count") != 0 or
                    not isinstance(snapshot.get("verified_pids"), list)):
                report["issues"].append("INVENTORY_UNTRUSTED")
                break
            visible = {}
            for item in snapshot["verified_pids"]:
                key = _identity(item)
                if key[0] in visible:
                    raise ValueError("duplicate observed PID")
                visible[key[0]] = key
            report["samples_completed"] += 1
            if any(pid in visible and visible[pid] != base
                   for pid, base in expected_by_pid.items()):
                report["issues"].append("PID_REUSED_OR_IDENTITY_CHANGED")
                break
            active = sorted(pid for pid, base in expected_by_pid.items()
                            if visible.get(pid) == base)
            if active:
                consecutive_absence = 0
                report["issues"] = ["EXPECTED_PROCESS_STILL_ACTIVE"]
            else:
                consecutive_absence += 1
                if consecutive_absence >= 2:
                    report["observed_exit_pids"] = sorted(expected_by_pid)
                    # Only tracked identities are absent; handle closure remains unproven.
                    report["state"] = "EXPECTED_PIDS_ABSENT_UNPROVEN"
                    report["issues"] = []
                    break
                report["issues"] = ["AWAITING_SECOND_ABSENCE_SAMPLE"]
            if index < samples - 1:
                sleeper(pause_seconds)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
        report["state"] = "BLOCKED"
        report["issues"] = [type(exc).__name__]
    return report
