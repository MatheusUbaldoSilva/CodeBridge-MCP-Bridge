"""Independent CodeBridge GUI recovery after externally verified shutdown.

Does not perform an installation or mutate RAG data.
"""
from __future__ import annotations
import subprocess
import time
import ntpath
from pathlib import Path

from installer.rag_p9b_restart_readiness import inspect_restart_prerequisites


def recover_gui(installed: Path, *, launch=None, probe=None,
                sleep=time.sleep, attempts=20) -> dict:
    result=dict(state="RECOVERY_UNVERIFIED", launched=False,
                installer_executed=False, index_modified=False)
    root=Path(installed).resolve()
    files=inspect_restart_prerequisites(root)
    if files["state"]!="RESTART_FILES_OBSERVED_ONLY":
        return {**result,"reason":"RESTART_FILES_UNVERIFIED"}
    if launch is None:
        # Prevent two CodeBridge GUI instances after a partial shutdown.
        try:
            import psutil
            expected=ntpath.normcase(ntpath.normpath(str(
                root/"app_rewrite"/"main.py")))
            for proc in psutil.process_iter(attrs=["name","cmdline"]):
                parts=proc.info.get("cmdline")
                name=str(proc.info.get("name") or "").lower()
                if parts is None and "python" in name:
                    return {**result,"reason":"GUI_PROCESS_IDENTITY_UNVERIFIED"}
                if parts and expected in {
                    ntpath.normcase(ntpath.normpath(str(x).strip('"')))
                    for x in parts
                }:
                    return {**result,"reason":"GUI_ALREADY_RUNNING"}
        except (OSError,ValueError,psutil.Error):
            return {**result,"reason":"GUI_PROCESS_ENUMERATION_FAILED"}
        def launch(args,cwd):
            flags=getattr(subprocess,"DETACHED_PROCESS",0)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            return subprocess.Popen(args,cwd=cwd,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    if probe is None:
        import psutil
        def probe(pid):
            try:
                p=psutil.Process(pid)
                return p.is_running() and any("main.py" in str(x).lower() for x in p.cmdline())
            except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):
                return False
    try:
        app=root/"app_rewrite"/"main.py"
        pythonw=root/"runtime"/"python"/"pythonw.exe"
        p=launch([str(pythonw),str(app)],str(app.parent))
        pid=int(p.pid)
        if pid<=0:
            return {**result,"reason":"RESTART_PID_UNVERIFIED"}
        for i in range(attempts):
            if probe(pid):
                return {**result,"state":"GUI_PROCESS_RECOVERED",
                        "launched":True,"pid":pid,
                        "mcp_handshake_verified":False}
            sleep(0.25)
        return {**result,"state":"RECOVERY_PENDING",
                "launched":True,"pid":pid,"reason":"GUI_START_NOT_CONFIRMED"}
    except (OSError,ValueError,TypeError):
        return {**result,"reason":"GUI_LAUNCH_FAILED"}
