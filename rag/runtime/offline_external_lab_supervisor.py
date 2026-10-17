"""External laboratory observer for one explicitly spawned synthetic child."""
from __future__ import annotations

import subprocess
import sys
import time

_CHILD = (
    "import sys,time;"
    "print('LAB_CHILD_READY',flush=True);"
    "signal=sys.stdin.readline().strip();"
    "sys.exit(0 if signal=='LAB_STOP' else 3)"
)

def run_external_synthetic_observer(*, timeout=5):
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or not 0 < timeout <= 20:
        raise ValueError("invalid lab timeout")
    report = {
        "state": "BLOCKED",
        "child_pid": None,
        "cooperative_stop": False,
        "exit_observed": False,
        "copy_authorized": False,
        "all_handles_closed": False,
        "production_quiescence_proven": False,
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", _CHILD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    report["child_pid"] = proc.pid
    try:
        ready = proc.stdout.readline().strip()
        if ready != "LAB_CHILD_READY":
            return report
        proc.stdin.write("LAB_STOP\n")
        proc.stdin.flush()
        proc.wait(timeout=timeout)
        report["cooperative_stop"] = True
        report["exit_observed"] = proc.poll() == 0
        if report["exit_observed"]:
            report["state"] = "LAB_COOPERATIVE_EXIT_OBSERVED_UNPROVEN"
        return report
    except (OSError, subprocess.TimeoutExpired):
        return report
    finally:
        if proc.poll() is None:
            # Never terminate an unrelated PID; retain process object identity.
            proc.stdin.close()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Escalation only for child created by this function.
                proc.terminate()
                proc.wait(timeout=timeout)
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
