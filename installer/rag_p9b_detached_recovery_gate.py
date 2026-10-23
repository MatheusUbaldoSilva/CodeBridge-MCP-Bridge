"""Fail-closed identity and process boundary for detached lab recovery."""
import hashlib
import json
import os
from pathlib import Path

def verify_boundary(*, marker, journal, installer_pid, supervisor_pid, lab):
    refused={"state":"DETACHED_RECOVERY_BOUNDARY_REFUSED","verified":False}
    try:
        root=Path(lab).resolve()
        identity=json.loads(Path(marker).read_text(encoding="utf-8"))
        if (identity.get("purpose")!="P9B_DISPOSABLE_UNIFIED_LAB"
                or identity.get("lab")!=str(root)
                or not root.is_dir() or root.is_symlink()):
            return {**refused,"reason":"LAB_IDENTITY_INVALID"}
        if not isinstance(supervisor_pid,int) or supervisor_pid!=os.getpid():
            return {**refused,"reason":"SUPERVISOR_PID_NOT_ATTESTED"}
        if (not isinstance(installer_pid,int) or installer_pid<=0
                or supervisor_pid==installer_pid):
            return {**refused,"reason":"PROCESS_SEPARATION_UNVERIFIED"}
        proof=Path(journal)
        if not proof.is_file() or proof.is_symlink() or proof.stat().st_size>1024*1024:
            return {**refused,"reason":"JOURNAL_INVALID"}
        lines=proof.read_text(encoding="utf-8").splitlines()
        if (not lines or json.loads(lines[0]).get("state")!="SHELL_NSIS_LAB_INTERRUPTED"):
            return {**refused,"reason":"INTERRUPTION_UNVERIFIED"}
        return {"state":"DETACHED_RECOVERY_BOUNDARY_VERIFIED","verified":True,
                "lab":str(root),"journal_sha256":hashlib.sha256(proof.read_bytes()).hexdigest()}
    except Exception:
        return {**refused,"reason":"BOUNDARY_EXCEPTION"}
