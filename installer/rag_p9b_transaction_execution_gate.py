"""Read-only independent execution gate for the bound P9-B transaction.

A validated identity never implies authorization. This gate verifies
external stopped-process evidence and exact artifact identity, but it
cannot install, restore or alter the current Windows installation.
"""
from __future__ import annotations

from installer.rag_p9b_transaction_identity import verify_identity
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_crash_recovery_gate import inspect_crash_recovery

def assess_execution_gate(*, identity, identity_sha, installed, journal=None,
                          identity_probe=verify_identity,
                          poststop_probe=check_poststop,
                          crash_probe=inspect_crash_recovery):
    denied={"state":"P9B_EXECUTION_GATE_REFUSED","authorized":False,
            "read_only":True,"nsis_executed":False,"installed_modified":False}
    try:
        proof=identity_probe(identity,identity_sha)
        if (proof.get("verified") is not True or
                proof.get("state")!="TRANSACTION_IDENTITY_VERIFIED"):
            return {**denied,"reason":"BOUND_TRANSACTION_IDENTITY_INVALID"}
        stopped=poststop_probe(installed)
        if (stopped.get("state")!="POSTSTOP_OBSERVED_ONLY"
                or stopped.get("observed_stopped") is not True):
            return {**denied,"reason":"INDEPENDENT_POSTSTOP_UNVERIFIED",
                    "poststop_state":stopped.get("state")}
        if journal is not None:
            # A prior crash journal is a blocker, not authorization to
            # overwrite anything or create a second transaction.
            return {**denied,"reason":"RECOVERY_JOURNAL_REQUIRES_REVIEW"}
        return {**denied,"state":"P9B_EXECUTION_GATES_OBSERVED_ONLY",
                "identity_verified":True,"poststop_verified":True,
                "requires_external_elevation_and_rollback_executor":True}
    except Exception as exc:
        return {**denied,"reason":"GATE_EVIDENCE_EXCEPTION",
                "exception_type":type(exc).__name__}
