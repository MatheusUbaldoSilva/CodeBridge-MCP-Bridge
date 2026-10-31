"""DQ-E-F-4: source/process topology observer, not live module attestation."""
from __future__ import annotations
from pathlib import Path

def review_gui_process_topology_dev(processes:list[dict], dev_root:Path)->dict:
    if not isinstance(processes,list) or not isinstance(dev_root,Path):
        raise ValueError("invalid observation")
    normalized=[]
    for p in processes:
        if not isinstance(p,dict):
            raise ValueError("invalid process record")
        pid=p.get("ProcessId")
        ppid=p.get("ParentProcessId")
        cmd=p.get("CommandLine")
        if type(pid) is not int or pid<=0 or type(ppid) is not int or ppid<0 or not isinstance(cmd,str):
            raise ValueError("malformed process record")
        normalized.append((pid,ppid,cmd.replace("/","\\").casefold()))
    if len({p[0] for p in normalized})!=len(normalized):
        raise ValueError("duplicate PID observation")
    root=str(dev_root).replace("/","\\").casefold().rstrip("\\")
    app=root+"\\app_rewrite\\main.py"
    mcp=root+"\\author_mcp\\mcp_server.py"
    launch=[p for p in normalized if "codebridge-launcher\\launcher.py" in p[2]]
    gui=[p for p in normalized if app in p[2] and "--no-elevate" in p[2]]
    servers=[p for p in normalized if mcp in p[2] and "--port 8765" in p[2]]
    ids={p[0]:p for p in normalized}
    def descended(pid,ancestor):
        observed=set()
        while pid in ids and pid not in observed:
            observed.add(pid)
            if pid==ancestor:
                return True
            pid=ids[pid][1]
        return False
    matches=bool(launch and gui and servers and any(
        descended(g[0],l[0]) and descended(m[0],g[0])
        for l in launch for g in gui for m in servers
    ))
    return {
        "state":"GUI_PROCESS_TOPOLOGY_OBSERVED_ONLY" if matches
                else "GUI_PROCESS_TOPOLOGY_UNRESOLVED",
        "expected_dev_process_tree_observed":matches,
        "launcher_candidates":len(launch),
        "gui_candidates":len(gui),
        "mcp_candidates":len(servers),
        "loaded_python_module_attested":False,
        "gui_runtime_attested":False,
        "activation_authorized":False,"operational_use_allowed":False,
        "read_only":True,
    }
