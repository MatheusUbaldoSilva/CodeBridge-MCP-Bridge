"""One-shot, operator-approved production RAG generation trial.

Runs against the live public MCP and MUST roll back to legacy after probing.
Does not deploy, restart processes, delete source, or mark V1 released.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v1_public_readiness import _audit, _call


BASE = "v1_base_6142ab6e3b534f"
CANDIDATE = "v1_delta_bebee8b8a49943"
FINGERPRINT = "b8757eb7f10b32ac1728ff10dfb4fd54f352d5b691ac7a88bb26262a57418e2c"


async def _post_switch_proof() -> dict:
    status = await _call("codebridge_rag_status", {})
    index = status.get("index") or {}
    projects = status.get("projects") or []
    if (index.get("state") != "READY" or index.get("generation") != CANDIDATE
            or not projects or projects[0].get("document_count") != 211
            or projects[0].get("chunk_count") != 8778):
        raise RuntimeError("public MCP did not select correct candidate index")
    integrity = await _call("codebridge_rag_integrity", {})
    observed = integrity.get("details") or {}
    if (integrity.get("operation_ok") is not True
            or observed.get("state") != "OBSERVED_CONSISTENT"
            or observed.get("audited_generation") != CANDIDATE
            or observed.get("documents") != 211
            or observed.get("chunks") != 8778):
        raise RuntimeError("public candidate cross-store integrity did not pass")
    query = await _call("codebridge_search_context", {
        "project": "codebridge",
        "query": "read-only cross-store Qdrant sqlite pickletools UUID integrity manifest",
        "source_types": ["CODE"], "top_k": 12,
    })
    if query.get("operation_ok") is not True or query.get("effective_route") != "CODE":
        raise RuntimeError("candidate semantic search did not pass")
    paths = [item.get("metadata", {}).get("path") for item in query.get("results", [])]
    if "rag/runtime/live_integrity.py" not in paths:
        raise RuntimeError("new indexed source not visible in public semantic result")
    return {
        "status": {"generation": CANDIDATE, "docs": 211, "chunks": 8778},
        "integrity": {"generation": CANDIDATE, "state": observed["state"]},
        "semantic_route": query["effective_route"],
        "hits": len(paths), "new_source_found": True,
    }


async def _post_rollback_proof() -> dict:
    status = await _call("codebridge_rag_status", {})
    index = status.get("index") or {}
    projects = status.get("projects") or []
    if (index.get("generation") != "legacy" or index.get("state") != "READY"
            or not projects or projects[0].get("document_count") != 210
            or projects[0].get("chunk_count") != 8761):
        raise RuntimeError("legacy not restored in live public MCP")
    check = await _call("codebridge_rag_integrity", {})
    d = check.get("details") or {}
    if (check.get("operation_ok") is not True or d.get("state") != "OBSERVED_CONSISTENT"
            or d.get("audited_generation") != "legacy" or d.get("chunks") != 8761):
        raise RuntimeError("rollback legacy integrity unverified")
    return {"generation": "legacy", "docs": 210, "chunks": 8761,
            "integrity": "OBSERVED_CONSISTENT"}


def run() -> int:
    if os.environ.get("CB_OPERATOR_SUPERVISED_APPROVED") != "yes":
        raise RuntimeError("explicit supervised operator approval required")
    expected_pid = int(os.environ["CB_EXPECT_MCP_PID"])
    root = Path(os.environ["LOCALAPPDATA"]) / "CodeBridge" / "rag"
    repo = Path(os.environ["USERPROFILE"]) / "CodeBridge-MCP-Bridge"
    if (root / "active-generation.json").exists() or (root / "production-generation-transition.json").exists():
        raise RuntimeError("production has prior active pointer/journal")
    before = asyncio.run(_audit(concurrent=True))
    if before.get("state") != "PUBLIC_HYBRID_CONCURRENCY_PASS":
        raise RuntimeError("fresh public MCP concurrency proof failed")
    if before["public_reader"].get("public_server_pid") != expected_pid:
        raise RuntimeError("public MCP PID differs from expected live process")
    from rag.runtime.production_generation_transition import (
        publish_validated_generation, revert_active_to_legacy,
        rollback_pending_to_legacy,
    )
    from rag.runtime.production_supervised_trial import assess_supervised_trial
    authorization = "CODEBRIDGE_RAG_V1_ACTIVATE:" + CANDIDATE
    receipt = root / "generations" / CANDIDATE / "generation-receipt.json"
    fresh_record = {
        "schema_version": 1, "state": "PUBLIC_HYBRID_CONCURRENCY_PASS_READONLY",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": CANDIDATE,
        "candidate_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
        "activation_permitted": False,
        "public_proof": before,
    }
    evidence = {
        "schema_version": 1,
        "operator_authorization": authorization,
        "authorization_scope": "APPROVED_SOURCE_CHANGES_AND_SUPERVISED_TRIAL_WITH_ROLLBACK",
        "rollback_rehearsal": "REAL_WIN32_GENERATION_TRANSITION_TESTS_PASS",
        "source_review_fingerprint": FINGERPRINT,
        "candidate_receipt_sha256": fresh_record["candidate_receipt_sha256"],
        "public_mcp_pid": expected_pid,
        "public_readiness": fresh_record,
    }
    ready = assess_supervised_trial(BASE, CANDIDATE, evidence)
    if ready["state"] != "READY_FOR_SUPERVISED_TRIAL" or not ready["safe_to_activate"]:
        raise RuntimeError("supervised gate blocked: " + str(ready["blockers"]))
    # Exact approval was supplied by the user in this conversation.
    # Always return to legacy; this is a live trial, NOT a release.
    report = {
        "state": "TRIAL_STARTED",
        "candidate": CANDIDATE,
        "public_pid": expected_pid,
        "git_head": None,
        "trial_authorized": True,
        "production_release_approved": False,
        "live_public_preflight": before,
        "candidate_public_proof": None,
        "rollback": None,
        "legacy_public_post_rollback": None,
        "activation_permitted_after_trial": False,
    }
    switched = False
    error = None
    try:
        print("SUPERVISED_LIVE_POINTER_TRIAL_BEGIN", flush=True)
        publish_result = publish_validated_generation(
            baseline=BASE, candidate=CANDIDATE,
            operator_authorization=authorization,
            public_reader_attestation={
                "generation_lock_enabled": True, "mcp_restart_confirmed": True,
            },
            trial_evidence=evidence,
        )
        switched = True
        report["publish_result"] = publish_result
        print("LIVE_POINTER_ACTIVATED_PENDING_QUERY_PROOF", flush=True)
        report["candidate_public_proof"] = asyncio.run(_post_switch_proof())
        print("PUBLIC_CANDIDATE_SEMANTIC_PASS", flush=True)
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)[:550]
        print("LIVE_TRIAL_ERROR_REQUIRES_ROLLBACK", error, flush=True)
    finally:
        # If a partial transition exists, readers are already fail-closed
        # through the journal; never hand-edit the pointer.
        journal = root / "production-generation-transition.json"
        pointer = root / "active-generation.json"
        try:
            if journal.exists():
                report["rollback"] = rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            elif pointer.exists():
                report["rollback"] = revert_active_to_legacy(
                    baseline=BASE, expected_candidate=CANDIDATE,
                    operator_authorization="CODEBRIDGE_RAG_V1_ROLLBACK:" + CANDIDATE,
                )
            else:
                report["rollback"] = {"state": "LEGACY_UNCHANGED"}
            print("POST_TRIAL_LEGACY_ROLLBACK",report["rollback"]["state"],flush=True)
        except Exception as rollback_error:
            print("CRITICAL_ROLLBACK_ERROR",repr(rollback_error),flush=True)
            raise
    report["legacy_public_post_rollback"] = asyncio.run(_post_rollback_proof())
    report["state"] = (
        "LIVE_TRIAL_PASSED_AND_ROLLED_BACK"
        if not error and report["candidate_public_proof"]
        else "LIVE_TRIAL_FAILED_AND_ROLLED_BACK"
    )
    if error:
        report["candidate_error"] = error
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if (root / "active-generation.json").exists() or (root / "production-generation-transition.json").exists():
        raise RuntimeError("pointer or journal remains after trial")
    out = repo / "docs" / "RAG_V1_03_C_SUPERVISED_LIVE_TRIAL_2026-10-19.json"
    if out.exists():
        raise RuntimeError("existing live trial receipt; refuse overwrite")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print("LIVE_SUPERVISED_TRIAL_RESULT", json.dumps({
        "state": report["state"], "candidate": CANDIDATE,
        "rollback": report["rollback"]["state"],
        "legacy": report["legacy_public_post_rollback"],
        "receipt": str(out),
    }, ensure_ascii=True), flush=True)
    return 0 if report["state"] == "LIVE_TRIAL_PASSED_AND_ROLLED_BACK" else 3


if __name__ == "__main__":
    sys.exit(run())
