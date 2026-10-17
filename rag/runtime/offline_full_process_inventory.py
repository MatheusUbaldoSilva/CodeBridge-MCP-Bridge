"""Sanitized full Windows process inventory, read-only and non-authorizing.

Collects every visible Win32_Process, not only recognized RAG services.
Avoids CommandLine and raw paths in reports.
"""
from __future__ import annotations

import hashlib
import json
import subprocess

_SCRIPT = (
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CreationDate | "
    "ConvertTo-Json -Compress -Depth 3"
)


def inspect_full_process_inventory(*, runner=None):
    runner = runner or subprocess.run
    report = {"state": "BLOCKED", "identity_inventory_ok": False,
              "verified_pids": [], "unverified_count": 0,
              "kernel_pid_zero_excluded": 0,
              "copy_authorized": False, "all_handles_closed": False,
              "production_quiescence_proven": False}
    try:
        result = runner(["powershell.exe", "-NoProfile", "-NonInteractive",
                         "-Command", _SCRIPT], capture_output=True, text=True,
                        timeout=20, check=True)
        payload = json.loads(result.stdout)
        rows = payload if isinstance(payload, list) else [payload]
        if not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError("empty or invalid inventory")
        seen = set()
        for row in rows:
            pid = row.get("ProcessId")
            ppid = row.get("ParentProcessId")
            born = row.get("CreationDate")
            exe = row.get("ExecutablePath")
            name = row.get("Name")
            if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0 or pid in seen:
                raise ValueError("duplicate or invalid PID")
            seen.add(pid)
            if pid == 0:
                report["kernel_pid_zero_excluded"] += 1
                continue
            if not isinstance(ppid, int) or isinstance(ppid, bool) or ppid < 0:
                report["unverified_count"] += 1
                continue
            if not born or not exe or not name:
                report["unverified_count"] += 1
                continue
            report["verified_pids"].append({
                "pid": pid, "parent_pid": ppid, "name": str(name).casefold(),
                "created_at": str(born),
                "executable_fingerprint": hashlib.sha256(
                    str(exe).casefold().encode("utf-8")).hexdigest()
            })
        report["verified_pids"].sort(key=lambda item: item["pid"])
        # OS process metadata is not always readable; still fail closed.
        report["identity_inventory_ok"] = report["unverified_count"] == 0
        report["state"] = ("FULL_INVENTORY_UNPROVEN" if report["identity_inventory_ok"]
                           else "BLOCKED")
    except (ValueError, TypeError, OSError, subprocess.SubprocessError) as exc:
        report["error_type"] = type(exc).__name__
    return report
