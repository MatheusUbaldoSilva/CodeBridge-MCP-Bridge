"""Fail-closed CodeBridge shell recovery via injected, pre-audited backend.

No default mutation backend is supplied. Runtime updates require an
independent executable, validated stopped-process proof and explicit
approval. This component never accesses winreg directly.
"""
from __future__ import annotations

from installer.rag_p9b_shell_restore_plan import build_shell_restore_plan


def execute_shell_restore(snapshot, *, appdata, desktop, expected_sha256,
                          stopped_verified=False, independent=False,
                          execute=False, backend=None,
                          journal=None, postverify=None):
    base={"state":"SHELL_RESTORE_REFUSED","restored":False,
          "registry_modified":False,"shortcuts_modified":False}
    if not (stopped_verified is True and independent is True and execute is True):
        return {**base,"reason":"RECOVERY_GATES_MISSING"}
    if backend is None or journal is None or postverify is None:
        return {**base,"reason":"INDEPENDENT_BACKEND_JOURNAL_AND_POSTVERIFY_REQUIRED"}
    plan=build_shell_restore_plan(snapshot,appdata=appdata,desktop=desktop,
        expected_snapshot_sha256=expected_sha256,installed_stopped=True)
    if plan.get("state")!="SHELL_RESTORE_PLAN_ONLY":
        return {**base,"reason":"RESTORE_PLAN_UNVERIFIED",
                "plan_reason":plan.get("reason")}
    try:
        journal("SHELL_RESTORE_ARMED",plan)
        # One atomic backend transaction is required. Partial completion
        # must raise rather than claim success.
        outcome=backend(plan,snapshot)
        if not isinstance(outcome,dict) or outcome.get("verified") is not True:
            journal("SHELL_RESTORE_UNVERIFIED",{})
            return {**base,"state":"SHELL_RESTORE_REVIEW_REQUIRED",
                    "reason":"BACKEND_COMPLETION_UNVERIFIED"}
        proof=postverify(plan,snapshot)
        if not isinstance(proof,dict) or proof.get("verified") is not True:
            journal("SHELL_RESTORE_POSTVERIFY_FAILED",{})
            return {**base,"state":"SHELL_RESTORE_REVIEW_REQUIRED",
                    "reason":"INDEPENDENT_POSTVERIFY_FAILED"}
        journal("SHELL_RESTORE_VERIFIED",{"postverified":True})
        return {**base,"state":"SHELL_RESTORE_VERIFIED",
                "restored":True,
                "registry_modified":outcome.get("registry_modified") is True,
                "shortcuts_modified":outcome.get("shortcuts_modified") is True}
    except Exception as error:
        try:
            journal("SHELL_RESTORE_EXCEPTION",{"type":type(error).__name__})
        except Exception:
            pass
        return {**base,"state":"SHELL_RESTORE_REVIEW_REQUIRED",
                "reason":"TRANSACTION_EXCEPTION"}
