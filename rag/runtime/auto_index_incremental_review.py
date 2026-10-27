"""RAG-AUTO-05-B: approved-generation delta proposal, read-only.

A successful proposal is NOT permission to copy embeddings. Candidate
approval, baseline integrity, model compatibility, and actual vector
provenance are distinct checks. No automatic promotion is implemented.
"""
from __future__ import annotations

from pathlib import Path

from rag.runtime.auto_index_incremental_plan import (
    IncrementalPlanError, compare_frozen_inventories,
)
from rag.runtime.auto_index_queue import get_job
from rag.runtime.auto_index_approval import (
    read_reviewed_sources, revalidate_auto_index_preview,
)
from rag.runtime.auto_index_generation import verify_prepared_auto_generation
from rag.runtime.auto_index_incremental_manifest import inspect_reusable_manifest_chunks


def plan_reviewed_incremental_delta(
    queue_path: Path, baseline_job_id: str, candidate_job_id: str, *,
    baseline_text_model: str, candidate_text_model: str,
    baseline_code_model: str, candidate_code_model: str,
) -> dict:
    """Validate actual receipts before computing a non-mutating source delta."""
    if baseline_job_id == candidate_job_id:
        raise IncrementalPlanError("baseline and candidate must differ")
    baseline_job = get_job(queue_path, baseline_job_id)
    candidate_job = get_job(queue_path, candidate_job_id)
    if baseline_job is None or candidate_job is None:
        raise IncrementalPlanError("unregistered job")
    if baseline_job["project_id"] != candidate_job["project_id"]:
        raise IncrementalPlanError("cross-project comparison forbidden")
    if baseline_job["project_id"] == "codebridge":
        raise IncrementalPlanError("public codebridge project is reserved")
    if baseline_job["source_root"] != candidate_job["source_root"]:
        raise IncrementalPlanError("source root mismatch")
    if baseline_job["requested_scope"] != candidate_job["requested_scope"]:
        raise IncrementalPlanError("scope mismatch")
    if (not baseline_job["approved"] or not candidate_job["approved"]
            or baseline_job["state"] != "READY_FOR_REVIEW"
            or candidate_job["state"] not in ("QUEUED", "PAUSED", "READY_FOR_REVIEW")):
        raise IncrementalPlanError("jobs must be approved and in reviewed states")
    verified = verify_prepared_auto_generation(queue_path, baseline_job_id)
    if (verified.get("verified") is not True
            or verified.get("project_id") != baseline_job["project_id"]):
        raise IncrementalPlanError("baseline generation is not verified for project")
    old = read_reviewed_sources(queue_path, baseline_job_id)
    new = read_reviewed_sources(queue_path, candidate_job_id)
    if verified.get("source_revision") != old.get("review_sha256"):
        raise IncrementalPlanError("verified baseline source revision mismatch")
    for job, receipt in ((baseline_job, old), (candidate_job, new)):
        if (receipt.get("source_root") != job["source_root"]
                or receipt.get("scope") != job["requested_scope"]):
            raise IncrementalPlanError("review receipt does not match job")
    # Refresh the exact approved candidate bytes, denying any subsequent edits.
    revalidate_auto_index_preview({
        "schema_version": 1,
        "project_id": candidate_job["project_id"],
        "source_root": new["source_root"],
        "scope": new["scope"],
        "sources": new["sources"],
        "review_sha256": new["review_sha256"],
    })
    plan = compare_frozen_inventories(
        {"schema_version": 1, "sources": old["sources"]},
        {"schema_version": 1, "sources": new["sources"]},
        baseline_text_model=baseline_text_model,
        candidate_text_model=candidate_text_model,
        baseline_code_model=baseline_code_model,
        candidate_code_model=candidate_code_model,
    )
    receipt = inspect_reusable_manifest_chunks(
        verified, old, plan["eligible_reuse_sources"],
        text_model_revision=baseline_text_model,
        code_model_revision=baseline_code_model,
    )
    return {
        **plan,
        "candidate_reuse_chunk_receipt": receipt,
        "project_id": candidate_job["project_id"],
        "baseline_job_id": baseline_job_id,
        "candidate_job_id": candidate_job_id,
        "baseline_verified": True,
        "candidate_receipt_revalidated": True,
        "generation_activated": False,
        "public_pointer_updated": False,
    }
