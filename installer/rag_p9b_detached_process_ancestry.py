"""Fail-closed detached process ancestry attestation.

Requires external runtime *and* a process chain disjoint from CodeBridge.
No process signaling, installation, registry or filesystem mutations.
"""
from __future__ import annotations
from pathlib import Path
import os


def inspect_detached_process_ancestry(*,installed,process=None,process_api=None):
    blocked={"state":"EXTERNAL_ANCESTRY_UNVERIFIED","verified":False,
             "read_only":True,"shutdown_authorized":False}
    try:
        if process_api is None:
            import psutil
            process_api=psutil
        root=Path(installed).resolve(strict=True)
        current=process if process is not None else process_api.Process()
        visited=set()
        inspected=0
        while current is not None:
            pid=current.pid
            if not isinstance(pid,int) or pid<=0 or pid in visited or inspected>64:
                return {**blocked,"reason":"INVALID_PROCESS_CHAIN"}
            visited.add(pid)
            inspected+=1
            executable=Path(current.exe()).resolve(strict=True)
            if executable.is_relative_to(root):
                return {**blocked,"reason":"PROCESS_INSIDE_INSTALLED_APP"}
            try:
                command=current.cmdline()
            except Exception:
                # Access to command lines of Windows core service processes can
                # be denied even when the executable path is independently
                # verifiable. Only allow exact protected System32 binaries.
                system32=(Path(os.environ.get("WINDIR",r"C:\Windows"))/
                          "System32")
                allowed={"svchost.exe","services.exe","wininit.exe"}
                if (executable.name.lower() not in allowed
                        or executable != (
                            system32/executable.name).resolve(strict=True)):
                    return {**blocked,"reason":"PROCESS_CMDLINE_UNAVAILABLE"}
                command=[]
            if not isinstance(command,list):
                return {**blocked,"reason":"PROCESS_CMDLINE_UNAVAILABLE"}
            for part in command:
                if not isinstance(part,str):
                    return {**blocked,"reason":"PROCESS_CMDLINE_INVALID"}
                try:
                    token=Path(part)
                    if token.is_absolute() and token.exists() and token.resolve().is_relative_to(root):
                        return {**blocked,"reason":"PROCESS_EXECUTES_INSTALLED_APP"}
                except (OSError,ValueError):
                    return {**blocked,"reason":"PROCESS_CMDLINE_INVALID"}
            current=current.parent()
        return {**blocked,"state":"EXTERNAL_PROCESS_ANCESTRY_VERIFIED",
                "verified":True,"processes_inspected":inspected}
    except Exception:
        return {**blocked,"reason":"PROCESS_ANCESTRY_UNAVAILABLE"}
