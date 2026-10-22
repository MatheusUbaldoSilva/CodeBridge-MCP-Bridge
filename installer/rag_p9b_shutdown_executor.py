"""Externally driven, identity-fenced graceful shutdown; NEVER installs NSIS.

Execution requires an exact live plan digest. Caller must run from an
independent recovery channel, not from the MCP this would shut down.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
from pathlib import Path

from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan

WM_CLOSE = 0x0010


def execute_shutdown(installed, *, expected_digest, execute=False,
                     independent=False, psutil_module=None,
                     gui_close=None, sleep=time.sleep):
    result = dict(state="SHUTDOWN_REFUSED", processes_stopped=False,
                  installer_executed=False, installation_modified=False)
    if execute is not True or independent is not True:
        return {**result, "reason": "INDEPENDENT_EXECUTION_REQUIRED"}
    import psutil
    ps = psutil_module or psutil
    try:
        records = [proc.info for proc in ps.process_iter(
            attrs=["pid", "ppid", "name", "exe", "cmdline", "create_time"])]
        plan = make_shutdown_plan(Path(installed), records=records)
        if plan["state"] != "SHUTDOWN_PLAN_ONLY":
            return {**result, "reason": "CURRENT_PLAN_UNVERIFIED"}
        if plan["identity_digest"] != expected_digest:
            return {**result, "reason": "IDENTITY_DIGEST_CHANGED"}
        processes = {item["component"]: ps.Process(item["pid"])
                     for item in plan["processes"]}
        # All identities verified before the FIRST signal.
        for item in plan["processes"]:
            proc = processes[item["component"]]
            if abs(proc.create_time()-item["create_time"]) > 0.001:
                return {**result, "reason": "PID_REUSED"}
        if gui_close is None:
            if os.name != "nt":
                return {**result,"reason":"WINDOWS_REQUIRED"}
            def gui_close(pid):
                user32=ctypes.windll.user32
                found=[]
                @ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
                def each(hwnd,_):
                    target=ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(target))
                    if target.value==pid and user32.IsWindowVisible(hwnd):
                        buf=ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(hwnd,buf,256)
                        if buf.value=="CodeBridge 2.0 - MCP Bridge":
                            found.append(hwnd)
                    return True
                user32.EnumWindows(each,None)
                if len(found)!=1:
                    return False
                return bool(user32.PostMessageW(found[0],WM_CLOSE,0,0))
        gui=processes["GUI"]
        if not gui_close(gui.pid):
            return {**result,"reason":"GUI_WM_CLOSE_FAILED"}
        for _ in range(50):
            if not gui.is_running():
                break
            sleep(0.1)
        if gui.is_running():
            return {**result,"state":"PARTIAL_SHUTDOWN",
                    "reason":"GUI_GRACEFUL_TIMEOUT"}
        stopped=["GUI"]
        for role in ("MCP","ADAPTER","TUNNEL"):
            proc=processes[role]
            try:
                if not proc.is_running():
                    stopped.append(role)
                    continue
                if abs(proc.create_time()-next(i["create_time"] for i in plan["processes"]
                                                if i["component"]==role))>0.001:
                    return {**result,"state":"PARTIAL_SHUTDOWN",
                            "reason":"PID_REUSED_DURING_STOP","stopped":stopped}
                proc.terminate()
                proc.wait(timeout=4)
            except ps.NoSuchProcess:
                pass
            except ps.TimeoutExpired:
                return {**result,"state":"PARTIAL_SHUTDOWN",
                        "reason":"GRACEFUL_TIMEOUT","stopped":stopped}
            stopped.append(role)
        return {**result,"state":"SHUTDOWN_SIGNALS_COMPLETED",
                "processes_stopped":True,"stopped":stopped,
                "requires_official_process_guard":True}
    except (OSError, ValueError, KeyError, ps.AccessDenied, ps.NoSuchProcess):
        return {**result,"reason":"PROCESS_IDENTITY_OR_ACCESS_ERROR"}
