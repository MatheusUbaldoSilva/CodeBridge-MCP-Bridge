"""Lab-only scoped Windows CIM observation with sanitized output.

No process is stopped; no production quiescence or copy permission is inferred.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone

def observe_scoped_windows_pids(pids, *, runner=None, clock=None):
    response = {
        "state": "BLOCKED", "source": "WINDOWS_CIM_LAB_SCOPED",
        "scope_pids": [], "identity_inventory_ok": False,
        "unverified_count": 0, "verified_pids": [],
        "copy_authorized": False, "all_handles_closed": False,
        "production_quiescence_proven": False, "issues": []
    }
    try:
        if (not isinstance(pids, (list, tuple)) or not pids or len(pids) > 16 or
                any(type(pid) is not int or pid <= 0 for pid in pids) or
                len(set(pids)) != len(pids)):
            raise ValueError("invalid lab PID scope")
        scope = sorted(pids)
        response["scope_pids"] = scope
        get_time = clock or (lambda: datetime.now(timezone.utc))
        def timestamp():
            value = get_time()
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError("invalid observation clock")
            return value.astimezone(timezone.utc).isoformat()
        response["observed_start_utc"] = timestamp()
        clause = " OR ".join("ProcessId = %d" % i for i in scope)
        script = (
            "@(Get-CimInstance Win32_Process -Filter '" + clause +
            "' | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath) "
            "| ConvertTo-Json -Compress -Depth 3"
        )
        result = (runner or subprocess.run)(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20, check=True)
        response["observed_end_utc"] = timestamp()
        raw = json.loads(result.stdout) if result.stdout.strip() else []
        rows = raw if isinstance(raw, list) else ([] if raw is None else [raw])
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid CIM row")
            pid, parent = row.get("ProcessId"), row.get("ParentProcessId")
            born, exe = row.get("CreationDate"), row.get("ExecutablePath")
            if (type(pid) is not int or pid not in scope or pid in seen or
                    type(parent) is not int or parent < 0):
                raise ValueError("invalid CIM process identity")
            seen.add(pid)
            if not born or not exe:
                response["unverified_count"] += 1
                continue
            response["verified_pids"].append({
                "pid": pid, "parent_pid": parent, "created_at": str(born),
                "executable_fingerprint": hashlib.sha256(
                    str(exe).casefold().encode("utf-8")).hexdigest()
            })
        response["verified_pids"].sort(key=lambda row: row["pid"])
        if response["unverified_count"]:
            response["issues"].append("PROCESS_IDENTITY_UNAVAILABLE")
        else:
            response["identity_inventory_ok"] = True
            response["state"] = "SCOPED_CIM_OBSERVATION_UNPROVEN"
    except (ValueError, TypeError, OSError, KeyError, subprocess.SubprocessError) as exc:
        response["issues"].append(type(exc).__name__)
    return response
