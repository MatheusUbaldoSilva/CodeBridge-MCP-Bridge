"""RAG-DEL-01.04-E: classify interrupted swaps without modifying anything.

The output is an advisory review only. No state transition is authorized.
"""
from __future__ import annotations
from pathlib import Path
from rag.runtime.knowledge_deletion_recovery_lab import inspect_laboratory_transactions
from rag.runtime.knowledge_deletion_swap_lab import DeletionSwapError

def plan_lab_recovery(catalog_file: Path, public_pointer: Path) -> dict:
    transactions = inspect_laboratory_transactions(catalog_file, public_pointer)
    if not transactions:
        return {"state": "NO_PENDING_LAB_TRANSACTIONS", "plans": [],
                "writes_performed": False, "rollback_authorized": False}
    plans=[]
    for entry in transactions:
        state=entry["state"]
        disposition=entry["disposition"]
        if entry["requires_manual_review"]:
            action="MANUAL_INVESTIGATION_REQUIRED"
        elif state=="ROLLED_BACK" and disposition=="CATALOG_AT_OLD_REVISION":
            action="NO_ACTION"
        elif state=="PREPARED" and disposition=="CATALOG_AT_OLD_REVISION":
            action="RECONCILE_PREPARED_WITHOUT_SWITCH"
        elif state=="PREPARED" and disposition=="CATALOG_AT_NEW_REVISION":
            action="ROLLBACK_ELIGIBLE_AFTER_REVALIDATION"
        elif state=="ACTIVE" and disposition=="CATALOG_AT_NEW_REVISION":
            action="ACTIVE_TRANSACTION_REQUIRES_EXPLICIT_DECISION"
        else:
            action="MANUAL_INVESTIGATION_REQUIRED"
        plans.append({"transaction":entry["transaction"],
                      "journal_state":state, "disposition":disposition,
                      "recommended_action":action,
                      "automatic_repair_authorized":False})
    return {"state":"LAB_RECOVERY_REVIEW_ONLY","plans":plans,
            "writes_performed":False,"rollback_authorized":False}
