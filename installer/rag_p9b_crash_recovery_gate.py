"""Independent, read-only decision for interrupted P9-B shell rollback.

Never replays registry writes or deletes files. Refuses if any CodeBridge
process remains active or if the durable preimage and journal disagree.
"""
from __future__ import annotations

from installer.rag_p9b_crash_preimage import verify_crash_preimage
from installer.rag_p9b_rollback_journal import read_journal
from installer.p9b_update_process_guard import inspect_update_processes


_CRITICAL_STATES={"SHELL_BACKEND_ARMED","SHELL_BACKEND_PARTIAL_FAILURE",
                  "SHELL_BACKEND_WRITTEN","SHELL_BACKEND_RECOVERY_REVIEW_REQUIRED",
                  "SHELL_RESTORE_EXCEPTION","SHELL_RESTORE_ARMED"}
_TERMINAL={"SHELL_RESTORE_VERIFIED"}


def inspect_crash_recovery(*, preimage, preimage_sha, journal,
                           installed, process_guard=inspect_update_processes,
                           preimage_verifier=verify_crash_preimage,
                           journal_reader=read_journal):
    base={"state":"CRASH_RECOVERY_REFUSED","read_only":True,
          "recovery_authorized":False,"registry_modified":False,
          "shortcuts_modified":False}
    try:
        snapshot=preimage_verifier(preimage,preimage_sha)
        if snapshot.get("verified") is not True:
            return {**base,"reason":"PREIMAGE_UNVERIFIED"}
        events=journal_reader(journal)
        if events.get("state")!="JOURNAL_OBSERVED_ONLY" or not isinstance(events.get("count"),int):
            return {**base,"reason":"JOURNAL_UNVERIFIED"}
        if events["count"]<1:
            return {**base,"reason":"EMPTY_JOURNAL"}
        guard=process_guard(installed)
        if guard.get("state")!="NO_RUNNING_CODEBRIDGE":
            return {**base,"reason":"CODEBRIDGE_STILL_ACTIVE"}
        state=events.get("last_state")
        if state in _TERMINAL:
            return {**base,"state":"RECOVERY_ALREADY_VERIFIED_ONLY",
                    "reason":"TERMINAL_JOURNAL","journal_events":events["count"]}
        if state not in _CRITICAL_STATES:
            return {**base,"reason":"UNKNOWN_LAST_JOURNAL_STATE"}
        return {**base,"state":"CRASH_RESTORATION_REVIEW_REQUIRED",
                "preimage_verified":True,"journal_events":events["count"],
                "interrupted_state":state,
                "requires_external_operator":True,
                "requires_new_postrestore_verification":True}
    except Exception:
        return {**base,"reason":"INDEPENDENT_EVIDENCE_UNAVAILABLE"}
