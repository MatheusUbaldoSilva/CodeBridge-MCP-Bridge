"""Lab-only evidence summary. No report combination authorizes production copies."""
from __future__ import annotations


def summarize_lab_evidence(*, process_exit, handle_probe, restore_audit,
                           full_inventory=None):
    result = {"state": "BLOCKED", "issues": [], "evidence_complete": False,
              "copy_authorized": False, "publication_authorized": False,
              "production_quiescence_proven": False, "all_handles_closed": False}
    try:
        items = (process_exit, handle_probe, restore_audit)
        if any(not isinstance(x, dict) for x in items):
            raise ValueError("invalid report")
        for name, report in zip(("process", "handles", "restore"), items):
            mandatory_flag = ("production_authorized" if name == "restore"
                              else "copy_authorized")
            if report.get(mandatory_flag) is not False:
                result["issues"].append(name + "_MISSING_SAFE_FLAG")
            for flag in ("copy_authorized", "production_authorized", "publication_authorized",
                         "production_quiescence_proven", "all_handles_closed"):
                if flag in report and report[flag] is not False:
                    result["issues"].append(name + "_CLAIMS_AUTHORIZATION")
        if process_exit.get("state") != "EXPECTED_PIDS_ABSENT_UNPROVEN":
            result["issues"].append("PROCESS_EXIT_UNPROVEN")
        if (handle_probe.get("state") != "LAB_HANDLES_READABLE_UNPROVEN" or
                handle_probe.get("files_checked", 0) < 3):
            result["issues"].append("FILE_HANDLE_PROBE_UNPROVEN")
        if (restore_audit.get("state") != "LAB_RESTORE_EQUIVALENCE_UNPROVEN_FOR_PRODUCTION"
                or restore_audit.get("same_hashes") is not True
                or restore_audit.get("same_semantic_content") is not True):
            result["issues"].append("RESTORE_EQUIVALENCE_UNPROVEN")
        if full_inventory is not None:
            if (not isinstance(full_inventory, dict) or
                    full_inventory.get("identity_inventory_ok") is not True or
                    full_inventory.get("unverified_count") != 0):
                result["issues"].append("FULL_PROCESS_INVENTORY_UNTRUSTED")
        if not result["issues"]:
            result["state"] = "LAB_EVIDENCE_COLLECTED_NO_PRODUCTION_PROOF"
            result["evidence_complete"] = True
    except (TypeError, ValueError, KeyError) as exc:
        result["issues"] = [type(exc).__name__]
    return result
