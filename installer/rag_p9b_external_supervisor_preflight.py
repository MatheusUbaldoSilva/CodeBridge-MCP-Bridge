"""External supervisor read-only assessment of live CodeBridge processes.

No shutdown, installer launch, recovery, process adoption, or permissions
are granted here. An ambiguous process identity always blocks the cutover.
"""
from __future__ import annotations

import ntpath
from pathlib import Path


def _path(value):
    return ntpath.normcase(ntpath.normpath(str(value).strip('"')))


def assess_external_supervisor(installed: Path, *, records=None) -> dict:
    result = dict(state="SUPERVISOR_PREFLIGHT_UNVERIFIED",
                  inspection_only=True, safe_to_apply=False,
                  stop_authorized=False, installer_executed=False,
                  installed_modified=False, processes=[])
    root = Path(installed).resolve()
    if not root.is_dir():
        return {**result, "reason": "INSTALLED_ROOT_MISSING"}
    if records is None:
        try:
            import psutil
            records = [p.info for p in psutil.process_iter(
                attrs=["pid", "ppid", "name", "cmdline", "create_time"])]
        except Exception:
            return {**result, "reason": "PROCESS_ENUMERATION_FAILED"}
    scripts = {
        "GUI": _path(root/"app_rewrite"/"main.py"),
        "MCP": _path(root/"author_mcp"/"mcp_server.py"),
        "ADAPTER": _path(root/"author_mcp"/"adapter_server.py"),
        "TUNNEL": _path(root/"tools"/"tunnel-client.exe"),
    }
    found = []
    opaque = 0
    seen = set()
    births = {}
    try:
        for item in records:
            pid = int(item["pid"])
            if pid == 0:
                continue
            if pid <= 0 or pid in seen:
                return {**result, "reason": "DUPLICATE_OR_INVALID_PID"}
            seen.add(pid)
            cmdline = item.get("cmdline")
            if not isinstance(cmdline, (list, tuple)):
                opaque += 1
                continue
            arguments = {_path(token) for token in cmdline}
            matches = [kind for kind,path in scripts.items() if path in arguments]
            external_age = item.get("create_time")
            if external_age is not None:
                external_age = float(external_age)
                if 0 < external_age < float("inf"):
                    births[pid] = external_age
            if not matches:
                continue
            created = float(item["create_time"])
            if not (0 < created < float("inf")):
                return {**result, "reason": "PROCESS_CREATION_UNVERIFIED"}
            if len(matches) != 1:
                return {**result, "reason": "AMBIGUOUS_PROCESS_ROLE"}
            found.append(dict(component=matches[0], pid=pid,
                              parent_pid=int(item.get("ppid") or 0),
                              create_time=created))
    except (KeyError, TypeError, ValueError, OverflowError):
        return {**result, "reason": "PROCESS_IDENTITY_UNVERIFIED"}
    roles = {record["component"] for record in found}
    mcp_parent_unknown = sorted(
        record["pid"] for record in found
        if record["component"] == "MCP"
        and record["parent_pid"] not in seen
    )
    parent_age_conflicts = sorted(
        record["pid"] for record in found
        if record["parent_pid"] in births
        and births[record["parent_pid"]] > record["create_time"]
    )
    evidence = {"mcp_parent_absent": mcp_parent_unknown,
                "parent_age_conflicts": parent_age_conflicts}
    if not {"GUI", "MCP"}.issubset(roles):
        return {**result,
                "state": ("SUPERVISOR_PREFLIGHT_UNVERIFIED" if opaque
                          else "SUPERVISOR_TOPOLOGY_INCOMPLETE"),
                "reason": "OPAQUE_PROCESSES" if opaque else "KNOWN_COMPONENT_MISSING",
                "opaque_processes": opaque, "processes": found, **evidence}
    return {**result, "state": "SUPERVISOR_UPDATE_BLOCKED_RUNNING",
            "blockers": sorted(roles), "opaque_processes": opaque,
            "processes": found, **evidence}


def main(argv=None):
    import argparse
    import json
    p=argparse.ArgumentParser()
    p.add_argument("--install-root",required=True,type=Path)
    args=p.parse_args(argv)
    report=assess_external_supervisor(args.install_root)
    print(json.dumps(report,sort_keys=True))
    # This CLI intentionally never returns a deployment-allowing exit code.
    # An observed running stack is a blocker, not a successful cutover.
    return 2


if __name__=="__main__":
    raise SystemExit(main())
