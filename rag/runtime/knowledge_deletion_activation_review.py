"""RAG-DEL-01.04-I: consolidate verified evidence for manual activation review.

No side effects, no activation token, no catalog replacement.
"""
from __future__ import annotations
from hashlib import sha256
import json

class DeletionActivationReviewError(ValueError):
    pass

def compose_deletion_activation_review(
    preview:dict, preflight:dict, survivor_audit:dict,
    generation_row:dict, generation_receipt:dict,
) -> dict:
    fail=DeletionActivationReviewError
    if any(not isinstance(x,dict) for x in (
            preview,preflight,survivor_audit,generation_row,generation_receipt)):
        raise fail("missing evidence")
    project=preview.get("project_id")
    if not isinstance(project,str) or not project or project=="codebridge":
        raise fail("public or missing project")
    if (preview.get("mode")!="READ_ONLY_REMOVAL_PREVIEW"
            or preview.get("deletion_authorized") is not False
            or not isinstance(preview.get("selected_paths"),list)
            or not preview["selected_paths"]
            or preview["selected_paths"]!=sorted(set(preview["selected_paths"]))):
        raise fail("untrusted selection")
    if (preflight.get("state")!="PRIVATE_DELETION_PREFLIGHT_READ_ONLY"
            or preflight.get("project_id")!=project
            or preflight.get("expected_revision")!=preview.get("source_revision")
            or preflight.get("pending_deletion_transactions")!=0
            or preflight.get("activation_authorized") is not False):
        raise fail("catalog preflight not pinned")
    if (survivor_audit.get("state")!="PRIVATE_REMOVAL_AUDIT_ONLY"
            or survivor_audit.get("project_id")!=project
            or survivor_audit.get("activation_authorized") is not False
            or survivor_audit.get("catalog_modified") is not False
            or survivor_audit.get("vectors_verified")!=preview.get("chunks_to_preserve")
            or survivor_audit.get("documents_verified")!=preview.get("documents_to_preserve")):
        raise fail("candidate survivor audit incomplete")
    if (generation_row.get("index_family")!="RAG_DEL_01"
            or generation_row.get("project_id")!=project
            or generation_row.get("source_revision")!=generation_receipt.get("source_revision")
            or generation_receipt.get("project_id")!=project
            or generation_receipt.get("baseline_generation")!=preview.get("generation")
            or generation_receipt.get("selection_sha256")!=preview.get("review_sha256")
            or generation_receipt.get("vectors_verified")!=survivor_audit.get("vectors_verified")
            or generation_receipt.get("activation_authorized") is not False):
        raise fail("generation receipt does not match review")
    proof={"project_id":project,"baseline_revision":preview.get("source_revision"),
           "selected_paths":preview["selected_paths"],
           "selection_sha256":preview.get("review_sha256"),
           "lineage_sha256":survivor_audit.get("lineage_sha256"),
           "generation_receipt_sha256":generation_row.get("generation_receipt_sha256"),
           "catalog_sha256":preflight.get("old_catalog_sha256"),
           "public_pointer_sha256":preflight.get("public_pointer_sha256")}
    if any(not isinstance(x,str) or not x for x in proof.values() if not isinstance(x,list)):
        raise fail("incomplete pinned evidence")
    digest=sha256(json.dumps(proof,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return {"state":"DELETION_REVIEW_READY_BUT_NOT_AUTHORIZED",
            "project_id":project,"review_sha256":digest,
            "files_to_remove":len(preview["selected_paths"]),
            "preserved_vectors":survivor_audit["vectors_verified"],
            "activation_authorized":False,"catalog_modified":False,
            "operator_confirmation_required":True}
