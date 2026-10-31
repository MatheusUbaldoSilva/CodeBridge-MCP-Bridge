"""F-10: read-only GUI process lineage must also respect creation timestamps.

CIM creation timestamps are observed evidence, not a verified kernel PID/birth
identity binding. GUI modules and production RAG remain UNATTESTED.
"""
from __future__ import annotations
from pathlib import Path

from rag.runtime.knowledge_deletion_gui_process_observer_dev import (
    _script_command,review_gui_process_topology_dev,
)

def review_gui_creation_order_dev(processes:list[dict],dev_root:Path)->dict:
    topology=review_gui_process_topology_dev(processes,dev_root)
    records={}
    for item in processes:
        pid=item["ProcessId"]
        birth=item.get("CreationEpochMs")
        if type(birth) is not int or birth<=0:
            return dict(
                state="GUI_PROCESS_CREATION_ORDER_UNVERIFIED",
                process_creation_order_observed=False,
                installed_gui_runtime_attested=False,
                activation_authorized=False,operational_use_allowed=False,
                read_only=True,
            )
        records[pid]=(item["ParentProcessId"],birth,item["CommandLine"])
    root=str(dev_root).replace("/","\\").casefold().rstrip("\\")
    launch=str(dev_root.parent/"CodeBridge-Launcher"/"launcher.py").replace("/","\\").casefold()
    gui=root+"\\app_rewrite\\main.py"
    mcp=root+"\\author_mcp\\mcp_server.py"
    launcher=[pid for pid,(parent,birth,command) in records.items()
              if _script_command(command,launch)]
    guis=[pid for pid,(parent,birth,command) in records.items()
          if _script_command(command,gui,(("--no-elevate",""),))]
    mcps=[pid for pid,(parent,birth,command) in records.items()
          if _script_command(command,mcp,(("--port","8765"),))]
    def older_ancestor(descendant:int,ancestor:int)->bool:
        seen=set()
        current=descendant
        while current in records and current not in seen:
            seen.add(current)
            if current==ancestor:
                return True
            parent,birth,_=records[current]
            if parent not in records or records[parent][1]>birth:
                return False
            current=parent
        return False
    positive=(
        topology.get("expected_dev_process_tree_observed") is True
        and any(older_ancestor(g,l) and older_ancestor(m,g)
                for l in launcher for g in guis for m in mcps)
    )
    return dict(
        state="GUI_PROCESS_CREATION_ORDER_OBSERVED_ONLY" if positive
              else "GUI_PROCESS_CREATION_ORDER_UNVERIFIED",
        process_creation_order_observed=bool(positive),
        installed_gui_runtime_attested=False,
        loaded_python_module_attested=False,
        activation_authorized=False,operational_use_allowed=False,
        read_only=True,
    )
