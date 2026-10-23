"""Combine file and Windows shell rollback through explicit external workers.

No default production backend and no NSIS execution. The coordinator
never grants cutover authorization. Cross-subsystem postverification is
required after both workers report their own successful completion.
"""
from __future__ import annotations

from installer.rag_p9b_detached_combined_identity_gate import assess_detached_identity
from installer.rag_p9b_poststop_verification import check_poststop
from installer.rag_p9b_detached_process_ancestry import inspect_detached_process_ancestry


def recover_detached_combined(*, file_worker=None, shell_worker=None,
                              verify_worker=None, journal=None,
                              independent=False, execute=False,
                              production=False, identity_manifest=None,
                              identity_sha256=None, installed=None,
                              source_commit=None,
                              identity_gate=assess_detached_identity,
                              poststop_probe=check_poststop,
                              ancestry_probe=inspect_detached_process_ancestry):
    denied = {"state": "DETACHED_COMBINED_RECOVERY_REFUSED",
              "verified": False, "nsis_executed": False,
              "cutover_authorized": False}
    if (independent is not True or execute is not True
            or not all(callable(worker) for worker in
                       (file_worker, shell_worker, verify_worker, journal))):
        return {**denied, "reason": "INDEPENDENT_WORKERS_REQUIRED"}
    if production is True:
        if not all((identity_manifest, identity_sha256, installed, source_commit)):
            return {**denied, "reason": "BOUND_TRANSACTION_IDENTITY_REQUIRED"}
        try:
            ancestry = ancestry_probe(installed=installed)
        except Exception:
            return {**denied, "reason": "INDEPENDENT_PROCESS_ANCESTRY_REQUIRED"}
        if (not isinstance(ancestry, dict)
                or ancestry.get("state") != "EXTERNAL_PROCESS_ANCESTRY_VERIFIED"
                or ancestry.get("verified") is not True):
            return {**denied, "reason": "INDEPENDENT_PROCESS_ANCESTRY_REQUIRED"}
        try:
            bound = identity_gate(manifest=identity_manifest,
                                  manifest_sha256=identity_sha256,
                                  installed=installed,
                                  expected_source_commit=source_commit)
        except Exception:
            return {**denied, "reason": "IDENTITY_VERIFICATION_FAILED"}
        if (not isinstance(bound, dict)
                or bound.get("state") != "DETACHED_IDENTITY_OBSERVED_ONLY"
                or bound.get("identity_verified") is not True
                or bound.get("artifacts_checked") != 4
                or bound.get("cutover_authorized") is not False):
            return {**denied, "reason": "BOUND_TRANSACTION_IDENTITY_REQUIRED"}
        try:
            stopped = poststop_probe(installed)
        except Exception:
            return {**denied, "reason": "INDEPENDENT_POSTSTOP_UNAVAILABLE"}
        if (not isinstance(stopped, dict)
                or stopped.get("state") != "POSTSTOP_OBSERVED_ONLY"
                or stopped.get("observed_stopped") is not True):
            return {**denied, "reason": "INDEPENDENT_POSTSTOP_REQUIRED"}
    if (production is True and getattr(journal,"resumed",False) is True
            and getattr(journal,"bound_transaction_sha256",None)
                != str(identity_sha256).lower()):
        return {**denied, "reason":"RESUMED_JOURNAL_IDENTITY_UNVERIFIED"}
    def ancestry_still_independent():
        try:
            result = ancestry_probe(installed=installed)
        except Exception:
            return False
        return (isinstance(result, dict)
                and result.get("state")=="EXTERNAL_PROCESS_ANCESTRY_VERIFIED"
                and result.get("verified") is True)

    current = "FILES"
    try:
        if getattr(journal,"resumed",False) is not True:
            journal("SHELL_DETACHED_COMBINED_ARMED",
                    {"transaction_sha256":str(identity_sha256).lower()}
                    if production is True else {})
        if production is True and not ancestry_still_independent():
            journal("SHELL_DETACHED_ANCESTRY_RECHECK_FAILED", {"stage":"FILES"})
            return {**denied, "state":"DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason":"ANCESTRY_CHANGED_BEFORE_FILES"}
        files = file_worker()
        if (not isinstance(files, dict)
                or files.get("state") != "DETACHED_FILES_RESTORED_SHELL_PENDING"
                or files.get("verified") is not True
                or files.get("shell_restore_required") is not True):
            journal("SHELL_DETACHED_FILES_UNVERIFIED", {})
            return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason": "FILES_NOT_VERIFIED"}
        journal("SHELL_DETACHED_FILES_VERIFIED", {"postverified": True})
        current = "SHELL"
        if production is True:
            try:
                fresh_stop = poststop_probe(installed)
            except Exception:
                fresh_stop = None
            if (not isinstance(fresh_stop, dict)
                    or fresh_stop.get("state") != "POSTSTOP_OBSERVED_ONLY"
                    or fresh_stop.get("observed_stopped") is not True):
                journal("SHELL_DETACHED_POSTSTOP_RECHECK_FAILED", {})
                return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                        "reason": "POSTSTOP_LOST_BEFORE_SHELL"}
        if production is True and not ancestry_still_independent():
            journal("SHELL_DETACHED_ANCESTRY_RECHECK_FAILED", {"stage":"SHELL"})
            return {**denied, "state":"DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason":"ANCESTRY_CHANGED_BEFORE_SHELL"}
        shell = shell_worker()
        if (not isinstance(shell, dict)
                or shell.get("state") != "SHELL_RESTORE_VERIFIED"
                or shell.get("restored") is not True):
            journal("SHELL_DETACHED_SHELL_UNVERIFIED", {})
            return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason": "SHELL_NOT_VERIFIED"}
        journal("SHELL_DETACHED_SHELL_VERIFIED", {"postverified": True})
        current = "POSTVERIFY"
        if production is True:
            try:
                final_stop = poststop_probe(installed)
            except Exception:
                final_stop = None
            if (not isinstance(final_stop, dict)
                    or final_stop.get("state") != "POSTSTOP_OBSERVED_ONLY"
                    or final_stop.get("observed_stopped") is not True):
                journal("SHELL_DETACHED_FINAL_POSTSTOP_FAILED", {})
                return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                        "reason": "POSTSTOP_LOST_BEFORE_POSTVERIFY"}
        if production is True and not ancestry_still_independent():
            journal("SHELL_DETACHED_ANCESTRY_RECHECK_FAILED", {"stage":"POSTVERIFY"})
            return {**denied, "state":"DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason":"ANCESTRY_CHANGED_BEFORE_POSTVERIFY"}
        verified = verify_worker()
        if (not isinstance(verified, dict)
                or verified.get("verified") is not True):
            journal("SHELL_DETACHED_FINAL_POSTVERIFY_FAILED", {})
            return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                    "reason": "INDEPENDENT_POSTVERIFY_FAILED"}
        journal("SHELL_DETACHED_COMBINED_VERIFIED", {"postverified": True})
        return {**denied, "state": "DETACHED_COMBINED_RESTORE_VERIFIED",
                "verified": True, "production_authorized": False,
                "requires_public_mcp_recheck": True}
    except Exception as error:
        try:
            journal("SHELL_DETACHED_COMBINED_EXCEPTION",
                    {"type": type(error).__name__})
        except Exception:
            pass
        return {**denied, "state": "DETACHED_COMBINED_REVIEW_REQUIRED",
                "reason": "WORKER_OR_JOURNAL_EXCEPTION",
                "failed_stage": current}
