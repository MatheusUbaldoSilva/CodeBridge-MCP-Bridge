"""NSIS P9-B update transaction plan, fail closed and read-only.

This module specifies post-shutdown dependencies but deliberately has
no API for launching installers or restoring installed files.
"""
from __future__ import annotations


def plan_transaction(*, artifact, shutdown, poststop, independent_online,
                     official_process_state, paired_commit=None):
    denied={"state":"P9B_TRANSACTION_REFUSED",
            "installer_executed":False,
            "installed_modified":False,
            "rollback_performed":False,
            "authorized":False}
    if artifact.get("state")!="ARTIFACT_PAIR_VERIFIED_ONLY" or not artifact.get("paired"):
        return {**denied,"reason":"ARTIFACT_PAIR_UNVERIFIED"}
    if paired_commit != artifact.get("source_commit"):
        return {**denied,"reason":"SOURCE_COMMIT_MISMATCH"}
    if shutdown.get("state")!="SHUTDOWN_SIGNALS_COMPLETED" or shutdown.get("processes_stopped") is not True:
        return {**denied,"reason":"SHUTDOWN_UNVERIFIED"}
    if poststop.get("state")!="POSTSTOP_OBSERVED_ONLY" or poststop.get("observed_stopped") is not True:
        return {**denied,"reason":"POSTSTOP_UNVERIFIED"}
    if independent_online is not True:
        return {**denied,"reason":"EXTERNAL_RECOVERY_CHANNEL_UNAVAILABLE"}
    if official_process_state!="NO_RUNNING_CODEBRIDGE":
        return {**denied,"reason":"OFFICIAL_PROCESS_GUARD_NOT_CLEAR"}
    return {**denied,"state":"P9B_TRANSACTION_STEPS_OBSERVED_ONLY",
            "requires_fresh_hash_and_guard":True,
            "requires_registry_and_shortcut_restore_plan":True,
            "requires_public_postinstall_handshake":True,
            "steps":["REVALIDATE_PAIR_AND_NSIS_GUARD",
                     "RUN_NSIS_WITH_EXTERNAL_JOURNAL",
                     "VERIFY_INSTALLER_EXIT_AND_NEW_FILES",
                     "RECOVER_GUI_ADAPTER_MCP_TUNNEL",
                     "VERIFY_PUBLIC_CHATGPT_HANDSHAKE",
                     "ABORT_OR_ROLLBACK_ON_ANY_FAILED_GATE"]}
