"""Coordinate existing file and shell recovery in an isolated P9-B lab.

No production IO, NSIS or real HKCU. Two independently supplied workers
must pass their own validation before the combined result can be verified.
"""
from __future__ import annotations

def recover_combined_lab(*, file_worker, shell_worker, verify_worker, journal,
                         lab_attestation, independent=False):
    denied={"state":"COMBINED_LAB_RECOVERY_REFUSED","verified":False,
            "production_modified":False,"nsis_executed":False}
    if (independent is not True or not isinstance(lab_attestation,dict) or lab_attestation.get("purpose")!="P9B_DISPOSABLE_UNIFIED_LAB"
            or not all(callable(x) for x in (file_worker,shell_worker,verify_worker,journal))):
        return {**denied,"reason":"INDEPENDENT_LAB_GATES_REQUIRED"}
    try:
        journal("SHELL_COMBINED_RECOVERY_ARMED",{})
        files=file_worker()
        if not isinstance(files,dict):
            return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"FILE_WORKER_INVALID"}
        journal("SHELL_COMBINED_FILE_CHECKED",{"postverified":files.get("verified") is True})
        if files.get("verified") is not True or files.get("state")!="FILE_RESTORE_LAB_VERIFIED":
            return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"FILE_RESTORE_NOT_VERIFIED"}
        shell=shell_worker()
        if not isinstance(shell,dict):
            return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"SHELL_WORKER_INVALID"}
        journal("SHELL_COMBINED_SHELL_CHECKED",{"postverified":shell.get("verified") is True})
        if shell.get("verified") is not True or shell.get("state")!="SHELL_LAB_VERIFIED":
            return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"SHELL_RESTORE_NOT_VERIFIED"}
        post=verify_worker()
        if not isinstance(post,dict) or post.get("verified") is not True:
            return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"INDEPENDENT_POSTVERIFY_FAILED"}
        journal("SHELL_COMBINED_RECOVERY_VERIFIED",{"postverified":True})
        return {**denied,"state":"COMBINED_LAB_RECOVERY_VERIFIED","verified":True,
                "files":files.get("old_files"),"new_targets":files.get("new_files_removed"),
                "shortcuts":shell.get("shortcuts"),"fake_registry_keys":shell.get("registry_keys")}
    except Exception:
        return {**denied,"state":"COMBINED_LAB_REVIEW_REQUIRED","reason":"RECOVERY_OR_JOURNAL_EXCEPTION"}
