"""RAG-DEL fully evidence-gated temp-only catalog transition."""
from pathlib import Path
from rag.runtime.knowledge_deletion_audit_gate import audit_private_removal_candidate
from rag.runtime.knowledge_deletion_verified_swap_lab import laboratory_verified_swap

class DeletionEvidenceGateError(RuntimeError):
    pass

def laboratory_provenance_gated_swap(
    project_id: str, expected_revision: str, candidate: dict, preview: dict,
    baseline_manifest: Path, isolated_candidate_client, *,
    source_snapshot_root: Path,
    catalog_file: Path, public_pointer: Path,
    laboratory_mode: bool = False, operator_approved: bool = False,
) -> dict:
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("explicit laboratory approval required")
    if (candidate.get("project_id") != project_id or
            candidate.get("index_family") != "RAG_DEL_01" or
            preview.get("project_id") != project_id):
        raise DeletionEvidenceGateError("project provenance mismatch")
    # Verify the exact selected removal and every surviving vector before swap.
    proof = audit_private_removal_candidate(
        baseline_manifest, Path(candidate["generation_directory"]),
        project_id, preview, isolated_candidate_client,
        source_snapshot_root=source_snapshot_root,
    )
    if (proof["state"] != "PRIVATE_REMOVAL_AUDIT_ONLY"
            or proof["activation_authorized"] is not False
            or proof["catalog_modified"] is not False):
        raise DeletionEvidenceGateError("invalid deletion provenance evidence")
    switched = laboratory_verified_swap(
        project_id, expected_revision, candidate,
        catalog_file=catalog_file, public_pointer=public_pointer,
        operator_approved=True, laboratory_mode=True,
    )
    return {**switched, "lineage_sha256": proof["lineage_sha256"],
            "snapshot_inventory_sha256":proof["snapshot_inventory_sha256"],
            "semantic_vectors_checked": proof["vectors_verified"],
            "operational_use_allowed": False}
