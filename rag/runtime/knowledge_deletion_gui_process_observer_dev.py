"""DQ-E-F-4: read-only OS process topology, never a loaded GUI proof.

F-8 hardening parses Windows argv, checks actual script argv[1] and rejects
false-positive path strings embedded in -c, unrelated flags or comments.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from pathlib import Path

_shell32=ctypes.WinDLL("shell32",use_last_error=True)
_parse=_shell32.CommandLineToArgvW
_parse.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
_parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
_kernel=ctypes.WinDLL("kernel32",use_last_error=True)
_LocalFree=_kernel.LocalFree
_LocalFree.argtypes=[ctypes.c_void_p]
_LocalFree.restype=ctypes.c_void_p

def _windows_argv(line:str)->tuple[str,...]:
    if not isinstance(line,str) or not line or len(line)>32768:
        raise ValueError("malformed Windows command line")
    count=ctypes.c_int()
    buffer=_parse(line,ctypes.byref(count))
    if not buffer or count.value<1 or count.value>64:
        if buffer:_LocalFree(ctypes.cast(buffer,ctypes.c_void_p))
        raise ValueError("Windows command line cannot be parsed")
    try:
        return tuple(buffer[index] for index in range(count.value))
    finally:
        _LocalFree(ctypes.cast(buffer,ctypes.c_void_p))

def _script_command(line:str,expected:str,flags:tuple[str,...]=())->bool:
    args=_windows_argv(line)
    if len(args)<2 or args[0].replace("/","\\").rsplit("\\",1)[-1].casefold() not in (
            "python.exe","pythonw.exe"):
        return False
    script=args[1].replace("/","\\").casefold()
    if script!=expected:
        return False
    rest=args[2:]
    return all(
        flag in rest if not value else any(
            rest[i:i+2]==(flag,value) for i in range(len(rest)-1))
        for flag,value in flags
    )

def review_gui_process_topology_dev(processes:list[dict],dev_root:Path)->dict:
    if (not isinstance(processes,list) or not isinstance(dev_root,Path)
            or not dev_root.is_absolute()):
        raise ValueError("invalid observation")
    normalized=[]
    for p in processes:
        if not isinstance(p,dict):
            raise ValueError("invalid process record")
        pid=p.get("ProcessId")
        ppid=p.get("ParentProcessId")
        cmd=p.get("CommandLine")
        if type(pid) is not int or pid<=0 or type(ppid) is not int or ppid<0:
            raise ValueError("malformed process record")
        # Validate all argv at receipt time; never search raw command substrings.
        _windows_argv(cmd)
        normalized.append((pid,ppid,cmd))
    if len({p[0] for p in normalized})!=len(normalized):
        raise ValueError("duplicate PID observation")
    root=str(dev_root).replace("/","\\").casefold().rstrip("\\")
    app=root+"\\app_rewrite\\main.py"
    mcp=root+"\\author_mcp\\mcp_server.py"
    launcher=str(dev_root.parent/"CodeBridge-Launcher"/"launcher.py").replace("/","\\").casefold()
    launch=[p for p in normalized if _script_command(p[2],launcher)]
    gui=[p for p in normalized if _script_command(
        p[2],app,(("--no-elevate",""),))]
    servers=[p for p in normalized if _script_command(
        p[2],mcp,(("--port","8765"),))]
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
        "argv_script_paths_exactly_matched":matches,
        "loaded_python_module_attested":False,
        "gui_runtime_attested":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
        "read_only":True,
    }
