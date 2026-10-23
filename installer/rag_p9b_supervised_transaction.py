"""P9-B transaction supervisor with injectable IO; never invokes live NSIS.

A supervisor must verify every transition. Production installation is
explicitly unavailable until independent rollback execution is attested.
"""
from __future__ import annotations

def assess_transaction(*, release_evidence, poststop_evidence,
                       rollback_evidence, independent_channel):
    result={"state":"P9B_TRANSACTION_REFUSED","authorized":False,
            "installer_executed":False,"installed_modified":False}
    if (not isinstance(release_evidence,dict)
            or release_evidence.get("artifacts_verified") is not True
            or release_evidence.get("preimage_verified") is not True):
        return {**result,"reason":"BACKUP_EVIDENCE_INCOMPLETE"}
    if independent_channel is not True:
        return {**result,"reason":"INDEPENDENT_CHANNEL_UNAVAILABLE"}
    if (not isinstance(poststop_evidence,dict)
            or poststop_evidence.get("state")!="POSTSTOP_OBSERVED_ONLY"
            or poststop_evidence.get("observed_stopped") is not True):
        return {**result,"reason":"POSTSTOP_UNVERIFIED"}
    if (not isinstance(rollback_evidence,dict)
            or rollback_evidence.get("state")!="PRODUCTION_ROLLBACK_VERIFIED"
            or rollback_evidence.get("verified") is not True):
        return {**result,"reason":"PRODUCTION_ROLLBACK_NOT_PROVEN"}
    # A positive upstream attestation remains preparatory only. The actual
    # executor must independently revalidate hashes, elevation and NSIS guard.
    return {**result,"state":"TRANSACTION_GATES_OBSERVED_ONLY",
            "requires_fresh_elevated_executor_validation":True}


def rehearse_transaction(*, release_evidence, stop, rollback, restart,
                         external_ready=False, journal=None):
    """Injectable laboratory transaction: no default stop/install backend."""
    refused={"state":"TRANSACTION_REHEARSAL_REFUSED","completed":False,
             "installer_executed":False,"production_modified":False}
    if (external_ready is not True or not callable(journal)
            or not all(callable(x) for x in (stop,rollback,restart))
            or not isinstance(release_evidence,dict)
            or release_evidence.get("artifacts_verified") is not True
            or release_evidence.get("preimage_verified") is not True):
        return {**refused,"reason":"PRECONDITIONS_MISSING"}
    stopped=False
    try:
        journal("SHELL_REHEARSAL_ARMED",{})
        observed=stop()
        stopped=observed.get("verified") is True
        if not stopped:
            return {**refused,"reason":"STOP_PROOF_MISSING"}
        journal("SHELL_REHEARSAL_STOPPED",{})
        restored=rollback()
        if restored.get("verified") is not True:
            return {**refused,"state":"TRANSACTION_REHEARSAL_REVIEW_REQUIRED",
                    "reason":"ROLLBACK_POSTVERIFY_FAILED"}
        journal("SHELL_REHEARSAL_RESTORED",{})
        healthy=restart()
        if healthy.get("verified") is not True:
            return {**refused,"state":"TRANSACTION_REHEARSAL_REVIEW_REQUIRED",
                    "reason":"RESTART_UNVERIFIED"}
        journal("SHELL_REHEARSAL_COMPLETE",{})
        return {**refused,"state":"TRANSACTION_REHEARSAL_VERIFIED",
                "completed":True,"requires_real_nsis_and_public_handshake":True}
    except Exception:
        return {**refused,"state":"TRANSACTION_REHEARSAL_REVIEW_REQUIRED",
                "reason":"INDEPENDENT_OPERATION_EXCEPTION",
                "stop_observed":stopped}
