"""Reproducible genuine-NSIS interruption and independent recovery in TEMP.

Standalone disposable lab only. Does not open production installation,
registry or shortcuts. Recovery runs in a separate Python process.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

SENTINEL=b"P9B_GENUINE_NSIS_LAB_SENTINEL"
MARKER="P9B_NSIS_REPRO_"

def _write_event(path, state, **details):
    with Path(path).open("a",encoding="utf-8") as handle:
        handle.write(json.dumps({"state":state,**details},sort_keys=True)+"\n")
        handle.flush()
        os.fsync(handle.fileno())

def recover(lab, journal):
    lab=Path(lab).resolve()
    allowed=Path(tempfile.gettempdir()).resolve()
    events=Path(journal).read_text(encoding="utf-8").splitlines()
    if (lab.parent!=allowed or not lab.name.startswith(MARKER)
            or len(events)!=1 or json.loads(events[0]).get("state")!="SHELL_NSIS_INTERRUPTED"
            or json.loads(events[0]).get("lab")!=str(lab)):
        return False
    targets=list(lab.iterdir()) if lab.is_dir() else []
    if len(targets)!=1 or targets[0].name!="first.txt" or targets[0].is_symlink():
        return False
    if hashlib.sha256(targets[0].read_bytes()).hexdigest()!=hashlib.sha256(SENTINEL).hexdigest():
        return False
    targets[0].unlink()
    lab.rmdir()
    _write_event(journal,"SHELL_NSIS_ISOLATED_RECOVERED",verified=not lab.exists())
    return not lab.exists()

def run(*,makensis,staging,timeout_seconds=20):
    staging=Path(staging).resolve()
    if not staging.is_dir() or staging.is_symlink():
        raise ValueError("STAGING_INVALID")
    tag=MARKER+uuid.uuid4().hex
    lab=Path(tempfile.gettempdir()).resolve()/tag
    nsi=staging/(tag+".nsi")
    exe=staging/(tag+".exe")
    payload=staging/(tag+".txt")
    journal=staging/(tag+"_journal.jsonl")
    payload.write_bytes(SENTINEL)
    lines=['Unicode True','Name "P9B Repro NSIS Interrupt"',
           f'OutFile "{exe}"',f'InstallDir "{lab}"',
           'RequestExecutionLevel user','SilentInstall silent','Section',
           'SetOutPath "$INSTDIR"',f'File /oname=first.txt "{payload}"',
           'Sleep 15000',f'File /oname=second.txt "{payload}"','SectionEnd']
    nsi.write_text("\n".join(lines)+"\n",encoding="ascii")
    proc=None
    try:
        compiled=subprocess.run([str(makensis),str(nsi)],capture_output=True,timeout=timeout_seconds)
        if compiled.returncode:
            return {"state":"NSIS_LAB_COMPILE_FAILED","code":compiled.returncode}
        proc=subprocess.Popen([str(exe),"/S"])
        deadline=time.monotonic()+timeout_seconds
        while time.monotonic()<deadline and not (lab/"first.txt").is_file():
            if proc.poll() is not None:
                return {"state":"NSIS_LAB_EXITED_EARLY"}
            time.sleep(.05)
        if not (lab/"first.txt").is_file() or proc.poll() is not None:
            return {"state":"NSIS_LAB_FIRST_FILE_UNVERIFIED"}
        proc.kill()
        proc.wait(timeout=5)
        if (lab/"second.txt").exists():
            return {"state":"NSIS_LAB_NOT_INTERRUPTED"}
        _write_event(journal,"SHELL_NSIS_INTERRUPTED",lab=str(lab))
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),
            "--recover",str(lab),str(journal)],capture_output=True,timeout=timeout_seconds)
        return {"state":"REAL_NSIS_ISOLATED_RECOVERED" if child.returncode==0 else "NSIS_LAB_RECOVERY_UNVERIFIED",
                "recovery_exit":child.returncode,"lab_removed":not lab.exists(),
                "journal":str(journal),"installer_executed":True,
                "production_modified":False}
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        nsi.unlink(missing_ok=True)
        payload.unlink(missing_ok=True)

if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--recover":
        sys.exit(0 if recover(sys.argv[2],sys.argv[3]) else 2)
    raise SystemExit(2)
