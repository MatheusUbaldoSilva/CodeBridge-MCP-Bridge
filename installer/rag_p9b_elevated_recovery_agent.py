"""Detached privileged P9-B stop/restart rehearsal, never installs anything.

Launch from an elevated *independent* process with verified external
observation. An exact digest is required. Writes atomic recovery journal.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from installer.rag_p9b_supervised_shutdown_plan import make_shutdown_plan
from installer.rag_p9b_shutdown_executor import execute_shutdown
from installer.rag_p9b_external_recovery import recover_gui
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_poststart_health import check_local_poststart


def journal_write(path:Path, state:str, **items):
    path=Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    result={"state":state,"timestamp":time.time(),"pid":os.getpid(),**items}
    tmp=path.with_suffix(path.suffix+f".{os.getpid()}.tmp")
    try:
        with tmp.open("x",encoding="utf-8") as out:
            json.dump(result,out,sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(str(tmp),str(path))
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return result


def run_agent(installed, *, digest, journal, execute=False, external_ready=False,
              plan=make_shutdown_plan, stop=execute_shutdown,
              verify=check_poststop, recover=recover_gui,
              health=check_local_poststart, sleep=time.sleep,
              elevated_check=None):
    base={"installer_executed":False,"public_index_modified":False,
          "queue_initialized":False,"public_handshake_verified":False}
    def record(state, **kwargs):
        return journal_write(journal,state,**base,**kwargs)
    if not execute or not external_ready:
        return record("AGENT_DRY_RUN_ONLY",
                      reason="EXPLICIT_EXECUTION_AND_EXTERNAL_RECOVERY_REQUIRED")
    if elevated_check is None:
        def elevated_check():
            return os.name=="nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())
    try:
        if elevated_check() is not True:
            return record("AGENT_REFUSED",reason="ELEVATED_INTEGRITY_REQUIRED")
    except Exception:
        return record("AGENT_REFUSED",reason="INTEGRITY_UNVERIFIED")
    current=plan(installed)
    if current.get("state")!="SHUTDOWN_PLAN_ONLY" or current.get("identity_digest")!=digest:
        return record("AGENT_REFUSED",reason="PLAN_DIGEST_UNVERIFIED")
    record("PRE_SHUTDOWN_ARMED",digest=digest)
    started=False
    recovery=None
    poststop=None
    try:
        result=stop(installed,expected_digest=digest,execute=True,independent=True)
        started=result.get("processes_stopped") is True or result.get("state")=="PARTIAL_SHUTDOWN"
        record("SHUTDOWN_EVALUATED",stop_state=result.get("state"),
               stop_reason=result.get("reason"),recovery_needed=started)
        if not started:
            return record("AGENT_STOP_REFUSED",reason=result.get("reason"))
        if result.get("processes_stopped") is True:
            try:
                poststop=verify(installed)
                record("POSTSTOP_EVALUATED",poststop_state=poststop.get("state"),
                       observed_stopped=poststop.get("observed_stopped"))
            except Exception as exc:
                record("POSTSTOP_EXCEPTION",error=type(exc).__name__)
        # Recover regardless of partial stop or poststop outcome.
        try:
            recovery=recover(installed)
            record("GUI_RECOVERY_ATTEMPTED",recovery_state=recovery.get("state"),
                   recovery_pid=recovery.get("pid"))
        except Exception as exc:
            recovery={"state":"RECOVERY_EXCEPTION"}
            record("GUI_RECOVERY_EXCEPTION",error=type(exc).__name__)
        for attempt in range(30):
            try:
                local=health(installed)
                if local.get("verified") is True:
                    return record("LOCAL_MCP_RECOVERED_PUBLIC_RECHECK_REQUIRED",
                                  gui_state=recovery.get("state"),
                                  poststop_state=poststop.get("state") if poststop else None,
                                  local_state=local.get("state"))
            except Exception:
                pass
            sleep(0.5)
        return record("LOCAL_MCP_RECOVERY_UNVERIFIED",
                      gui_state=recovery.get("state"),
                      poststop_state=poststop.get("state") if poststop else None)
    except Exception as exc:
        # The stop function can raise after a successful GUI signal.
        # Never assume it is safe to skip recovery after the arm point.
        try:
            recovery=recover(installed)
            return record("AGENT_EXCEPTION_RECOVERY_ATTEMPTED",
                          error=type(exc).__name__,
                          recovery_state=recovery.get("state"))
        except Exception:
            return record("AGENT_EXCEPTION_RECOVERY_FAILED",
                          error=type(exc).__name__)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--install-root",type=Path,required=True)
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--digest",required=True)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--external-ready",action="store_true")
    args=p.parse_args(argv)
    result=run_agent(args.install_root,digest=args.digest,journal=args.journal,
                     execute=args.execute,external_ready=args.external_ready)
    print(json.dumps(result,sort_keys=True),flush=True)
    # Even recovered status is not a green light to install NSIS.
    return 2


if __name__=="__main__":
    raise SystemExit(main())
