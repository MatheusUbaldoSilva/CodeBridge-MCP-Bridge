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
