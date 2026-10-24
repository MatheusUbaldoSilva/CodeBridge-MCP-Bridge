"""Append-only fsync'd journal for a separately supervised P9-B rollback."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from installer.rag_p9b_journal_exclusive_lock import exclusive_journal_lock


def _reject_nonfinite_journal_number(value):
    raise ValueError("NONFINITE_JOURNAL_NUMBER")


def _strict_journal_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JOURNAL_KEY")
        result[key]=value
    return result


class RollbackJournal:
    def __init__(self,path):
        self.path=Path(path).absolute()
        if self.path.is_symlink() or not self.path.parent.is_dir():
            raise ValueError("JOURNAL_PATH_INVALID")
        self._sequence=0
        self.resumed=False
        self.bound_transaction_sha256=None
        if self.path.exists():
            raise FileExistsError("JOURNAL_ALREADY_EXISTS")
        with self.path.open("xb") as f:
            os.fsync(f.fileno())

    @classmethod
    def resume(cls,path,*,expected_transaction_sha256=None):
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
            history=[json.loads(line,object_pairs_hook=_strict_journal_pairs,parse_constant=_reject_nonfinite_journal_number) for line in path.read_text(encoding="utf-8").splitlines()]
            combined = history[0].get("state") == "SHELL_DETACHED_COMBINED_ARMED"
            if expected_transaction_sha256 is not None:
                expected=str(expected_transaction_sha256).lower()
                first=history[0].get("details",{}).get("transaction_sha256")
                if (len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected)
                        or first!=expected):
                    raise ValueError("JOURNAL_TRANSACTION_IDENTITY_MISMATCH")
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
                    "SHELL_DETACHED_COMBINED_ARMED",
                    "SHELL_DETACHED_LIFECYCLE_ARMED")):
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
        obj.resumed=True
        obj.bound_transaction_sha256=(
            str(expected_transaction_sha256).lower()
            if expected_transaction_sha256 is not None else None)
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
        if "transaction_sha256" in detail:
            value=detail["transaction_sha256"]
            if (not isinstance(value,str) or len(value)!=64
                    or any(c not in "0123456789abcdef" for c in value.lower())):
                raise ValueError("INVALID_TRANSACTION_SHA256")
            if (self._sequence!=0 or state not in (
                    "SHELL_DETACHED_COMBINED_ARMED",
                    "SHELL_DETACHED_LIFECYCLE_ARMED")):
                raise ValueError("TRANSACTION_SHA256_NOT_FIRST")
            safe["transaction_sha256"]=value.lower()
        entry={"seq":self._sequence+1,"state":state,
               "utc_epoch":time.time(),"details":safe}
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("JOURNAL_PATH_INVALID")
        # A resumed writer must never append on a journal changed by another
        # process (or replaced) since its last observed sequence.
        with exclusive_journal_lock(self.path):
            current=read_journal(self.path)
            if (current.get("state")!="JOURNAL_OBSERVED_ONLY"
                    or current.get("count")!=self._sequence):
                raise ValueError("JOURNAL_SEQUENCE_CHANGED")
            with self.path.open("ab") as f:
                f.write((json.dumps(entry,sort_keys=True)+chr(10)).encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
        self._sequence+=1
        return entry


def read_journal(path):
    p=Path(path)
    try:
        if not p.is_file() or p.is_symlink() or p.stat().st_size>1024*1024:
            return {"state":"JOURNAL_UNVERIFIED"}
        raw=p.read_bytes()
        # A valid JSON object without the terminating newline is not a
        # committed fsync journal record after a possible power loss.
        if raw and not raw.endswith(b"\n"):
            return {"state":"JOURNAL_UNVERIFIED"}
        entries=[json.loads(line,object_pairs_hook=_strict_journal_pairs,parse_constant=_reject_nonfinite_journal_number) for line in raw.decode("utf-8").splitlines()]
        if any(not isinstance(item,dict) or type(item.get("seq")) is not int or item["seq"]!=i+1 or not isinstance(item.get("state"),str) or not item["state"].startswith("SHELL_") or not isinstance(item.get("details"),dict) for i,item in enumerate(entries)):
            return {"state":"JOURNAL_UNVERIFIED"}
        return {"state":"JOURNAL_OBSERVED_ONLY","count":len(entries),
                "last_state":entries[-1]["state"] if entries else None}
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):
        return {"state":"JOURNAL_UNVERIFIED"}
