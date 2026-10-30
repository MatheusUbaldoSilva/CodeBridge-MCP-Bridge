"""Combined read-only candidate gate for RAG-DEL, no activation."""
from pathlib import Path
from rag.runtime.knowledge_deletion_lineage import verify_survivor_lineage
from rag.runtime.knowledge_deletion_semantics import verify_candidate_vector_semantics
from rag.runtime.knowledge_deletion_generation import digest_file
from rag.runtime.knowledge_deletion_snapshot import inspect_survivor_snapshot

def audit_private_removal_candidate(baseline_manifest:Path, candidate_dir:Path,
                                    project_id:str, preview:dict, isolated_client,
                                    *, source_snapshot_root:Path) -> dict:
    lineage=verify_survivor_lineage(
        baseline_manifest,Path(candidate_dir)/"rag-index-manifest.json",preview
    )
    snapshot=inspect_survivor_snapshot(
        source_snapshot_root,Path(candidate_dir)/"rag-index-manifest.json",
        project_id,
    )
    vectors=verify_candidate_vector_semantics(candidate_dir,project_id,isolated_client)
    if (lineage["preserved_chunks"]!=vectors["vectors_verified"]
            or lineage["preserved_documents"]!=vectors["documents_verified"]
            or snapshot["files_verified"]!=vectors["documents_verified"]
            or project_id!=preview.get("project_id")):
        raise ValueError("candidate source/vector provenance conflict")
    return {
        "state":"PRIVATE_REMOVAL_AUDIT_ONLY",
        "project_id":project_id,
        "lineage_sha256":lineage["lineage_sha256"],
        "snapshot_inventory_sha256":snapshot["snapshot_inventory_sha256"],
        "source_snapshot_files_verified":snapshot["files_verified"],
        "candidate_manifest_sha256":digest_file(
            Path(candidate_dir)/"rag-index-manifest.json"
        ),
        "documents_verified":vectors["documents_verified"],
        "vectors_verified":vectors["vectors_verified"],
        "activation_authorized":False,
        "public_pointer_updated":False,
        "catalog_modified":False,
    }
