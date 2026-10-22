"""Read-only process ownership topology for CodeBridge GUI and MCP.

Detects a potentially detached MCP before an operator closes the GUI;
does NOT terminate, restart, adopt or supervise any process.
"""
from __future__ import annotations

import json
import ntpath
from pathlib import Path


def _canonical(value: str) -> str:
    return ntpath.normcase(ntpath.normpath(value.strip().strip('"')))


def inspect_mcp_process_topology(installed: Path, *, process_records=None) -> dict:
    report = {
        "state": "MCP_OWNERSHIP_UNVERIFIED",
        "inspection_only": True,
        "safe_to_stop_processes": False,
        "processes_stopped": False,
        "installed_modified": False,
        "deployment_approved": False,
    }
    root = Path(installed).resolve()
    if not root.is_dir():
        return {**report, "reason": "INSTALL_ROOT_ABSENT"}
    if process_records is None:
        try:
            import psutil
            records = []
            for process in psutil.process_iter(attrs=[
                "pid", "ppid", "name", "cmdline",
            ]):
                info = process.info
                records.append(dict(info))
        except Exception:
            return {**report, "reason": "PROCESS_ENUMERATION_UNVERIFIED"}
    else:
        records = list(process_records)
    graph = {}
    gui = set()
    mcp = set()
    adapter = set()
    tunnel = set()
    names = {
        "GUI": _canonical(str(root/"app_rewrite"/"main.py")),
        "MCP": _canonical(str(root/"author_mcp"/"mcp_server.py")),
        "ADAPTER": _canonical(str(root/"author_mcp"/"adapter_server.py")),
        "TUNNEL": _canonical(str(root/"tools"/"tunnel-client.exe")),
    }
    try:
        for item in records:
            pid = int(item.get("pid"))
            ppid = int(item.get("ppid") or 0)
            if pid == 0:
                continue  # Windows System Idle Process
            if pid < 0 or ppid < 0 or pid in graph:
                return {**report, "reason": "DUPLICATE_OR_INVALID_PID"}
            graph[pid] = ppid
            cmd = item.get("cmdline") or []
            if not isinstance(cmd,(list,tuple)):
                return {**report, "reason": "PROCESS_CMDLINE_UNVERIFIED"}
            normalized = {_canonical(str(x)) for x in cmd}
            if names["GUI"] in normalized:
                gui.add(pid)
            if names["MCP"] in normalized:
                mcp.add(pid)
            if names["ADAPTER"] in normalized:
                adapter.add(pid)
            if names["TUNNEL"] in normalized:
                tunnel.add(pid)
    except (TypeError,ValueError,KeyError):
        return {**report, "reason": "PROCESS_RECORD_UNVERIFIED"}
    def inherited_from_gui(pid: int) -> bool:
        seen={pid}
        current=pid
        for _ in range(32):
            parent=graph.get(current,0)
            if parent in gui:
                return True
            if not parent or parent in seen:
                return False
            seen.add(parent)
            current=parent
        return False
    attached=sorted(pid for pid in mcp if inherited_from_gui(pid))
    detached=sorted(mcp-set(attached))
    lost_parent=sorted(pid for pid in detached if graph.get(pid,0) not in graph)
    output = {
        **report,
        "gui_pids": sorted(gui),
        "mcp_pids": sorted(mcp),
        "adapter_pids": sorted(adapter),
        "tunnel_pids": sorted(tunnel),
        "mcp_attached_to_gui": attached,
        "mcp_independent_of_current_gui": detached,
        "mcp_recorded_parent_absent": lost_parent,
        "active_mcp_count": len(mcp),
        "active_gui_count": len(gui),
        "still_requires_process_guard": bool(gui or mcp),
    }
    if not gui or not mcp:
        return {**output,"state":"MCP_GUI_TOPOLOGY_INCOMPLETE"}
    if detached:
        return {**output,"state":"MCP_INDEPENDENT_PROCESS_OWNERSHIP_UNVERIFIED"}
    return {**output,"state":"MCP_ATTACHED_TO_LIVE_GUI_OBSERVED"}


def main(argv=None) -> int:
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--install-root",type=Path,required=True)
    args=parser.parse_args(argv)
    value=inspect_mcp_process_topology(args.install_root)
    print(json.dumps(value,sort_keys=True))
    return 0 if value["state"] == "MCP_ATTACHED_TO_LIVE_GUI_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
