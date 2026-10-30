"""RAG-DEL-01.05: reject stale confirmations by rebuilding read-only previews."""
from __future__ import annotations
from pathlib import Path

from rag.runtime.knowledge_deletion_preview import preview_knowledge_removal
from rag.runtime.knowledge_deletion_preflight import inspect_private_deletion_preflight

class DeletionConfirmationStale(RuntimeError):
    pass

def recheck_deletion_confirmation(
    project_id:str, selected_paths:list[str], reviewed_preview_sha256:str,
    reviewed_catalog_sha256:str, reviewed_pointer_sha256:str, candidate:dict,
    *,catalog_file:Path, public_pointer:Path,
) -> dict:
    if (not isinstance(project_id,str) or project_id=="codebridge"
            or not isinstance(selected_paths,list) or not selected_paths
            or selected_paths!=sorted(set(selected_paths))
            or any(not isinstance(p,str) or not p for p in selected_paths)):
        raise DeletionConfirmationStale("invalid private selection")
    current=preview_knowledge_removal(project_id,selected_paths)
    if (current.get("project_id")!=project_id
            or current.get("selected_paths")!=selected_paths
            or current.get("deletion_authorized") is not False
            or current.get("candidate_created") is not False
            or current.get("review_sha256")!=reviewed_preview_sha256):
        raise DeletionConfirmationStale("deletion preview changed, review again")
    preflight=inspect_private_deletion_preflight(
        Path(catalog_file),Path(public_pointer),project_id,
        current["source_revision"],candidate,
    )
    if (preflight.get("old_catalog_sha256")!=reviewed_catalog_sha256
            or preflight.get("public_pointer_sha256")!=reviewed_pointer_sha256
            or preflight.get("activation_authorized") is not False):
        raise DeletionConfirmationStale("catalog or public pointer changed")
    return {
        "state":"DELETION_CONFIRMATION_RECHECKED_NOT_AUTHORIZED",
        "project_id":project_id,"selection_sha256":reviewed_preview_sha256,
        "source_revision":current["source_revision"],
        "catalog_sha256":reviewed_catalog_sha256,
        "public_pointer_sha256":reviewed_pointer_sha256,
        "activation_authorized":False,"catalog_modified":False,
        "additional_operator_confirmation_required":True,
    }
