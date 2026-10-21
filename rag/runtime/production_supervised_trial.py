"""Evidence-gated single-use RAG V1 production cutover trial.

Default production gate remains blocked. No side effects or public MCP calls:
all evidence is verified again under the exclusive Windows writer lock.
A supervised caller is responsible for fresh public probes and rollback.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from rag.runtime.production_cutover_gate import assess_real_cutover
from rag.runtime.production_content_review import summarize_versioned_source_review
from rag.runtime.status import resolve_rag_sqlite_path


_EXPECTED_POLICY_BLOCKERS = frozenset({
    "PUBLIC_MCP_READERS_RESTART_NOT_ATTESTED",
    "ATOMIC_PRODUCTION_POINTER_WRITER_AND_ROLLBACK_NOT_VALIDATED",
    "CHANGED_SOURCE_CONTENT_REVIEW_NOT_ATTESTED",
})
_ALLOWED_CHANGED = frozenset({
    "author_mcp/mcp_server.py",
    "author_mcp/rag_bridge.py",
    "rag/runtime/production_index.py",
    "rag/runtime/production_search.py",
    "rag/runtime/status.py",
})
_ALLOWED_ADDED = ("rag/runtime/live_integrity.py",)
# Separately reviewed incremental generation. Never relax the legacy path.
_INCREMENTAL_GENERATION = "v1_delta_3ab9c095605b4a"
_INCREMENTAL_ALLOWED_ADDED = ("rag/runtime/incremental_scheduler_gate.py",)
_INCREMENTAL_ALLOWED_CHANGED = _ALLOWED_CHANGED
_INCREMENTAL_EXPECTED_COUNTS = (211, 8774, 8774, 211)


def _matches_incremental_scope(candidate: str, validation: dict, content: dict) -> bool:
    return (
        candidate == _INCREMENTAL_GENERATION
        and tuple(validation.get(key) for key in (
            "documents", "chunks", "vectors", "manifest_entries"
        )) == _INCREMENTAL_EXPECTED_COUNTS
        and set(content.get("modified_paths", [])) == _INCREMENTAL_ALLOWED_CHANGED
        and tuple(content.get("added_paths", [])) == _INCREMENTAL_ALLOWED_ADDED
        and content.get("removed_paths") == []
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess_supervised_trial(
    baseline: str, candidate: str, evidence: dict[str, Any] | None
) -> dict[str, Any]:
    """Read-only fail-closed gate. Cannot turn a standalone 'autorizado' into access."""
    result = assess_real_cutover(baseline, candidate)
    output = dict(result)
    errors: list[str] = []
    proof = evidence if isinstance(evidence, dict) else {}
    state = resolve_rag_sqlite_path().resolve().parent
    root = state / "generations"
    # A successful reversible trial archives its candidate pointer.
    # Refuse replay even with a freshly constructed public proof and the
    # same previously authorized generation-specific string. This check
    # runs again under the publisher's exclusive writer lock.
    archived = state / ("recovered-pointer-" + candidate + ".json")
    if archived.exists():
        errors.append("SUPERVISED_TRIAL_ALREADY_CONSUMED")
    if not proof or proof.get("schema_version") != 1:
        errors.append("SUPERVISION_EVIDENCE_MISSING")
    if proof.get("operator_authorization") != "CODEBRIDGE_RAG_V1_ACTIVATE:" + candidate:
        errors.append("GENERATION_SPECIFIC_OPERATOR_AUTHORIZATION_MISSING")
    if proof.get("authorization_scope") != "APPROVED_SOURCE_CHANGES_AND_SUPERVISED_TRIAL_WITH_ROLLBACK":
        errors.append("OPERATOR_AUTHORIZATION_SCOPE_MISSING")
    if proof.get("rollback_rehearsal") != "REAL_WIN32_GENERATION_TRANSITION_TESTS_PASS":
        errors.append("REAL_WINDOWS_ROLLBACK_REHEARSAL_MISSING")
    expected = _EXPECTED_POLICY_BLOCKERS
    if set(result["blockers"]) != expected or "verified" not in result or not result["verified"].get("candidate"):
        errors.append("STANDARD_GATE_NOT_SAFELY_PROVEN")
    try:
        content = summarize_versioned_source_review(root / baseline, root / candidate)
        # Additional exact source/hash scope proof; never replaces the old,
        # stricter legacy trial policy or grants activation by itself.
        from rag.runtime.production_source_scope_attestation import inspect_approved_source_scope
        scope = inspect_approved_source_scope(
            content, proof.get("approved_source_sha256"),
            expected_fingerprint=proof.get("source_review_fingerprint"),
        )
        if scope["state"] != "SCOPE_MATCHED_NOT_AUTHORIZED":
            errors.append("EXACT_SOURCE_SCOPE_NOT_ATTESTED")
        incremental = _matches_incremental_scope(
            candidate, result["verified"]["candidate"]["validation"], content,
        )
        legacy = (set(content["modified_paths"]) == _ALLOWED_CHANGED
                  and tuple(content["added_paths"]) == _ALLOWED_ADDED
                  and not content["removed_paths"])
        if (content["evidence_sha256_not_signature"] != proof.get("source_review_fingerprint")
                or not (legacy or incremental)):
            errors.append("SOURCE_APPROVAL_SCOPE_OR_FINGERPRINT_MISMATCH")
    except (OSError, ValueError, KeyError) as exc:
        errors.append("SOURCE_REVIEW_INVALID:" + str(exc)[:140])
    try:
        receipt = root / candidate / "generation-receipt.json"
        if _sha(receipt) != proof.get("candidate_receipt_sha256"):
            errors.append("CANDIDATE_GENERATION_RECEIPT_CHANGED")
    except OSError:
        errors.append("CANDIDATE_RECEIPT_UNAVAILABLE")

    # This record comes from the installed MCP client, not a fabricated
    # boolean. Its freshness, loaded PID and all three results are required.
    evidence_record = proof.get("public_readiness")
    if not isinstance(evidence_record, dict):
        errors.append("PUBLIC_MCP_EVIDENCE_MISSING")
    else:
        try:
            observed_at = datetime.fromisoformat(evidence_record["recorded_at_utc"].replace("Z", "+00:00"))
            seconds = (datetime.now(timezone.utc) - observed_at).total_seconds()
            if not (0 <= seconds <= 600):
                errors.append("PUBLIC_MCP_EVIDENCE_EXPIRED")
            live = evidence_record["public_proof"]
            reader = live["public_reader"]
            status = live["status"]
            cross = live["cross_store_integrity"]
            query = live["hybrid_concurrent"]
            if not (
                evidence_record.get("state") == "PUBLIC_HYBRID_CONCURRENCY_PASS_READONLY"
                and evidence_record.get("candidate") == candidate
                and evidence_record.get("candidate_receipt_sha256") == proof.get("candidate_receipt_sha256")
                and evidence_record.get("activation_permitted") is False
                and live.get("state") == "PUBLIC_HYBRID_CONCURRENCY_PASS"
                and live.get("safe_to_activate") is False
                and live.get("index_pointer_updated") is False
                and reader.get("public_server_pid") == proof.get("public_mcp_pid")
                and isinstance(proof.get("public_mcp_pid"), int)
                and proof["public_mcp_pid"] > 0
                and reader.get("reader_pin_proved") is True
                and reader.get("semantic_worker_serialization_loaded") is True
                and reader.get("public_runtime_ready_for_hybrid_acceptance") is True
                and reader.get("generation") == "legacy"
                and status.get("generation") == "legacy"
                and status.get("documents") == 210 and status.get("chunks") == 8761
                and cross.get("state") == "OBSERVED_CONSISTENT"
                and cross.get("generation") == "legacy"
                and cross.get("documents") == 210 and cross.get("chunks") == 8761
                and len(query) == 3
                and all(q.get("ok") is True and q.get("route") == "HYBRID"
                        and q.get("results") == 3 and q.get("error_type") is None
                        for q in query)
            ):
                errors.append("PUBLIC_MCP_READER_OR_HYBRID_PROOF_INCOMPLETE")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors.append("PUBLIC_MCP_PROOF_MALFORMED:" + str(exc)[:140])
    if (state / "active-generation.json").exists() or (state / "production-generation-transition.json").exists():
        errors.append("LIVE_POINTER_OR_JOURNAL_PRESENT")
    if errors:
        output.update(state="BLOCKED", safe_to_activate=False,
                      blockers=sorted(set(result["blockers"])) + sorted(set(errors)),
                      supervised_trial=False)
        return output
    output.update(
        state="READY_FOR_SUPERVISED_TRIAL",
        safe_to_activate=True,
        blockers=[],
        supervised_trial=True,
        authorization_is_single_trial_only=True,
        production_release_approved=False,
    )
    return output
