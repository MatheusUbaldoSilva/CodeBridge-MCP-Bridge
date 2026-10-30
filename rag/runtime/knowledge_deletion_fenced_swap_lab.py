"""RAG-DEL-01.04-U: compose fenced provenance transition, SCRATCH ONLY.

This adapter does not support the operational catalog or any real deletion.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from rag.runtime.knowledge_deletion_swap_lab import _lab_paths
from rag.runtime.knowledge_deletion_writer_fence_lab import laboratory_writer_fence
from rag.runtime.knowledge_deletion_provenance_swap_lab import (
    laboratory_provenance_gated_swap,
)


class DeletionFencedTransitionError(RuntimeError):
    pass


def laboratory_fenced_provenance_transition(
    project_id: str, expected_revision: str,
    candidate: dict, preview: dict, baseline_manifest: Path,
    isolated_candidate_client, *,
    source_snapshot_root: Path,
    queue_path: Path,
    reviewed_supervisor_evidence: dict,
    generation_guard_factory,
    semantic_guard_factory,
    catalog_file: Path,
    public_pointer: Path,
    laboratory_mode: bool = False,
    operator_approved: bool = False,
) -> dict:
    """Require queue+both locks before running audited lab catalog CAS."""
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("explicit scratch fenced transition approval required")
    # Verify the catalog cannot escape the temp sandbox before locking anything.
    catalog, pointer = _lab_paths(catalog_file, public_pointer)
    if not isinstance(candidate, dict) or not isinstance(preview, dict):
        raise DeletionFencedTransitionError("invalid candidate review")
    if (not isinstance(project_id, str) or not project_id
            or project_id == "codebridge"
            or candidate.get("project_id") != project_id
            or preview.get("project_id") != project_id):
        raise DeletionFencedTransitionError("private project identity required")
    review = reviewed_supervisor_evidence
    queue_id = sha256(str(Path(queue_path).resolve()).encode("utf-8")).hexdigest()
    if (not isinstance(review, dict)
            or review.get("state") != "SUPERVISOR_OBSERVED_QUIET_READ_ONLY"
            or review.get("supervisor_observed_quiet") is not True
            or review.get("read_only") is not True
            or review.get("queue_barrier_held") is not False
            or review.get("activation_authorized") is not False
            or review.get("operational_use_allowed") is not False
            or review.get("blockers") != []
            or review.get("queue_identity_sha256") != queue_id
            or type(review.get("supervisor_generation")) is not int
            or review["supervisor_generation"] < 0):
        raise DeletionFencedTransitionError("valid quiet supervisor review required")
    with laboratory_writer_fence(
        queue_path, generation_guard_factory, semantic_guard_factory,
        laboratory_mode=True, operator_approved=True,
    ) as fence:
        if fence["supervisor_generation"] != review["supervisor_generation"]:
            raise DeletionFencedTransitionError("supervisor generation drift; review again")
        switched = laboratory_provenance_gated_swap(
            project_id, expected_revision, candidate, preview,
            baseline_manifest, isolated_candidate_client,
            source_snapshot_root=source_snapshot_root,
            catalog_file=catalog,
            public_pointer=pointer,
            laboratory_mode=True, operator_approved=True,
        )
        if (switched.get("state") != "LAB_SWAP_ACTIVE"
                or switched.get("operational_use_allowed") is not False
                or switched.get("public_pointer_updated") is not False):
            raise DeletionFencedTransitionError("unexpected lab transition result")
        return {
            **switched,
            "fence_state": fence["state"],
            "fence_lock_order": fence["lock_order"],
            "activation_authorized": False,
            "operational_use_allowed": False,
        }