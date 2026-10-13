"""Read-only Windows PID identity audit for offline RAG shutdown planning.

Process names alone cannot prove quiescence. This code never stops any process,
never returns copy authorization and does not print command lines or full paths.
"""
from __future__ import annotations
import hashlib
import json
import subprocess


_SCRIPT = (
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,Name,ExecutablePath,CreationDate,CommandLine | "
    "ConvertTo-Json -Compress -Depth 3"
)


def inspect_process_identities(*, runner=None):
    runner = runner or subprocess.run
    report = {"state": "BLOCKED", "verified_pids": [], "unverified_count": 0,
              "identity_inventory_ok": False, "copy_authorized": False,
              "production_quiescence_proven": False}
    try:
        completed = runner(["powershell.exe", "-NoProfile", "-NonInteractive",
                            "-Command", _SCRIPT],
                           capture_output=True, text=True, timeout=15, check=True)
        raw = json.loads(completed.stdout)
        processes = raw if isinstance(raw, list) else [raw]
        if not processes or any(not isinstance(row, dict) for row in processes):
            raise ValueError("invalid process listing")
        suspects = []
        for item in processes:
            name = str(item.get("Name") or "").casefold()
            command = str(item.get("CommandLine") or "").casefold()
            if not ("codebridge" in name or "mcp_server.py" in command or
                    "adapter_server.py" in command or "qdrant" in name or
                    "rag_index" in command):
                continue
            pid = item.get("ProcessId")
            born = item.get("CreationDate")
            exe = item.get("ExecutablePath")
            if not isinstance(pid, int) or pid <= 0 or not born or not exe:
                report["unverified_count"] += 1
                continue
            suspects.append({"pid": pid, "name": name,
                             "created_at": str(born),
                             "executable_fingerprint": hashlib.sha256(
                                 str(exe).casefold().encode("utf-8")).hexdigest()})
        report["verified_pids"] = sorted(suspects, key=lambda row: row["pid"])
        report["identity_inventory_ok"] = True
        report["state"] = ("BLOCKED" if suspects or report["unverified_count"]
                           else "NO_KNOWN_PROCESS_UNPROVEN")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        report["error_type"] = type(exc).__name__
    return report
