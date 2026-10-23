"""Append-only fsync'd journal for a separately supervised P9-B rollback."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class RollbackJournal:
    def __init__(self,path):
        self.path=Path(path).absolute()
        if self.path.is_symlink() or not self.path.parent.is_dir():
            raise ValueError("JOURNAL_PATH_INVALID")
        self._sequence=0
        if self.path.exists():
            raise FileExistsError("JOURNAL_ALREADY_EXISTS")
        with self.path.open("xb") as f:
            os.fsync(f.fileno())

    @classmethod
    def resume(cls,path):
        """Resume only an incomplete verified append-only journal."""
        path=Path(path).absolute()
        proof=read_journal(path)
        if (proof.get("state")!="JOURNAL_OBSERVED_ONLY"
                or proof.get("count",0)<1
                or proof.get("last_state") in (
                    "SHELL_COMBINED_RECOVERY_VERIFIED",
                    "SHELL_NSIS_ISOLATED_RECOVERED",
                    "SHELL_NSIS_FULL_SCOPE_RECOVERED",
                    "SHELL_DETACHED_COMBINED_VERIFIED")):
            raise ValueError("JOURNAL_NOT_RESUMABLE")
        # A terminal success anywhere in history cannot be followed by
        # more recovery events. Reject malformed or unscoped event names.
        try:
            history=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            combined = history[0].get("state") == "SHELL_DETACHED_COMBINED_ARMED"
            completed={"SHELL_COMBINED_RECOVERY_VERIFIED",
                "SHELL_NSIS_ISOLATED_RECOVERED",
                "SHELL_NSIS_FULL_SCOPE_RECOVERED",
                "SHELL_DETACHED_COMBINED_VERIFIED"}
            if not combined:
                completed.add("SHELL_PRODUCTION_FILE_RESTORED")
                if proof.get("last_state")=="SHELL_PRODUCTION_FILE_RESTORED":
                    raise ValueError("JOURNAL_NOT_RESUMABLE")
            if (history[0].get("state") not in (
                    "SHELL_COMBINED_RECOVERY_ARMED",
                    "SHELL_NSIS_LAB_INTERRUPTED",
                    "SHELL_NSIS_INTERRUPTED",
                    "SHELL_NSIS_FULL_SCOPE_INTERRUPTED",
                    "SHELL_DETACHED_COMBINED_ARMED")):
                raise ValueError("JOURNAL_INITIAL_STATE_INVALID")
            if (any(not isinstance(entry,dict)
                    or not isinstance(entry.get("state"),str)
                    or not entry["state"].startswith("SHELL_")
                    or entry["state"] in completed for entry in history)
                    or not all(isinstance(e.get("details"),dict) for e in history)):
                raise ValueError("JOURNAL_HISTORY_INVALID")
        except (OSError,ValueError,TypeError):
            raise ValueError("JOURNAL_HISTORY_INVALID") from None
        obj=cls.__new__(cls)
        obj.path=path
        obj._sequence=proof["count"]
        return obj

    def __call__(self,state,detail):
        if not isinstance(state,str) or not state.startswith("SHELL_"):
            raise ValueError("JOURNAL_STATE_REJECTED")
        if not isinstance(detail,dict):
            raise ValueError("JOURNAL_DETAIL_INVALID")
        # Never serialize registry values or shortcut content.
        safe={}
        for key in ("type","files","keys","postverified"):
            if key in detail and isinstance(detail[key],(str,bool,int)):
                safe[key]=detail[key]
        entry={"seq":self._sequence+1,"state":state,
               "utc_epoch":time.time(),"details":safe}
        with self.path.open("ab") as f:
            f.write((json.dumps(entry,sort_keys=True)+chr(10)).encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        self._sequence+=1
        return entry


def read_journal(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>1024*1024:
        return {"state":"JOURNAL_UNVERIFIED"}
    try:
        entries=[json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
        if any(item.get("seq")!=i+1 for i,item in enumerate(entries)):
            return {"state":"JOURNAL_UNVERIFIED"}
        return {"state":"JOURNAL_OBSERVED_ONLY","count":len(entries),
                "last_state":entries[-1]["state"] if entries else None}
    except (OSError,ValueError,KeyError,TypeError):
        return {"state":"JOURNAL_UNVERIFIED"}
