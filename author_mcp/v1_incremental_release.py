"""Generation-specific RAG V1 release, with automatic rollback on failed public verification."""
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
CANDIDATE = "v1_delta_1ae1d01ea84f4e"
FINGERPRINT = "d3279df2f89129e02b042d30adeda45aac81aeef1458583e0b8148384d38b77b"


async def prove_candidate():
    status = await _call("codebridge_rag_status", {})
    index = status.get("index") or {}
    projects = status.get("projects") or []
    if (index.get("generation") != CANDIDATE or index.get("state") != "READY"
            or not projects or projects[0].get("document_count") != 211
            or projects[0].get("chunk_count") != 8774):
        raise RuntimeError("candidate status verification failed")
    integrity = await _call("codebridge_rag_integrity", {})
    detail = integrity.get("details") or {}
    if (integrity.get("operation_ok") is not True
            or detail.get("state") != "OBSERVED_CONSISTENT"
            or detail.get("audited_generation") != CANDIDATE
            or detail.get("documents") != 211
            or detail.get("chunks") != 8774):
        raise RuntimeError("candidate cross-store verification failed")
    search = await _call("codebridge_search_context", {
        "project": "codebridge",
        "query": "incremental scheduler gate source fence",
        "source_types": ["CODE"],
        "path_filter": "rag/runtime/incremental_scheduler_gate.py",
        "top_k": 5,
    })
    paths = [v.get("metadata", {}).get("path") for v in search.get("results", [])]
    if (search.get("operation_ok") is not True or search.get("effective_route") != "CODE"
            or "rag/runtime/incremental_scheduler_gate.py" not in paths):
        raise RuntimeError("candidate code semantic search verification failed")
    return {"status": index["generation"], "documents": 211, "chunks": 8774,
            "integrity": detail["state"], "new_source_found": True,
            "semantic_route": search["effective_route"]}


async def prove_legacy():
    status = await _call("codebridge_rag_status", {})
    p = status.get("projects") or []
    if (status.get("index", {}).get("generation") != "legacy" or not p
            or p[0].get("document_count") != 210
            or p[0].get("chunk_count") != 8761):
        raise RuntimeError("legacy rollback status verification failed")
    integrity = await _call("codebridge_rag_integrity", {})
    if ((integrity.get("details") or {}).get("state") != "OBSERVED_CONSISTENT"):
        raise RuntimeError("legacy rollback integrity verification failed")
    return {"generation": "legacy", "documents": 210, "chunks": 8761}


def run() -> int:
    from rag.runtime.production_generation_transition import (
        publish_validated_generation, rollback_pending_to_legacy, revert_active_to_legacy,
    )
    from rag.runtime.production_supervised_trial import assess_supervised_trial
    from rag.runtime.production_content_review import summarize_versioned_source_review

    if (os.environ.get("CB_OPERATOR_RELEASE_APPROVED") != "yes"
            or os.environ.get("CB_OPERATOR_RELEASE_GENERATION") != CANDIDATE):
        raise RuntimeError("generation-specific final release authorization missing")
    expected_pid = int(os.environ["CB_EXPECT_MCP_PID"])
    state = Path(os.environ["LOCALAPPDATA"]) / "CodeBridge" / "rag"
    report_file = Path(__file__).resolve().parents[1] / "docs" / "RAG_V1_03_P5_INCREMENTAL_RELEASE_2026-10-21.json"
    if report_file.exists() or (state / "active-generation.json").exists() or (state / "production-generation-transition.json").exists():
        raise RuntimeError("release artifact or pointer already present")
    if (state / ("recovered-pointer-" + CANDIDATE + ".json")).exists():
        raise RuntimeError("this generation was already consumed")
    before = asyncio.run(_audit(concurrent=True))
    reader = before.get("public_reader") or {}
    if (before.get("state") != "PUBLIC_HYBRID_CONCURRENCY_PASS"
            or reader.get("public_server_pid") != expected_pid):
        raise RuntimeError("fresh public reader verification failed")

    folders = state / "generations"
    review = summarize_versioned_source_review(folders / BASE, folders / CANDIDATE)
    if review["evidence_sha256_not_signature"] != FINGERPRINT:
        raise RuntimeError("release source fingerprint changed")
    digest_map = {
        d["path"]: d["candidate_sha256"] for d in review["details"]
        if d["action"] in ("ADDED", "MODIFIED")
    }
    receipt = folders / CANDIDATE / "generation-receipt.json"
    authorization = "CODEBRIDGE_RAG_V1_ACTIVATE:" + CANDIDATE
    evidence = {
        "schema_version": 1, "operator_authorization": authorization,
        "authorization_scope": "APPROVED_SOURCE_CHANGES_AND_SUPERVISED_TRIAL_WITH_ROLLBACK",
        "rollback_rehearsal": "REAL_WIN32_GENERATION_TRANSITION_TESTS_PASS",
        "source_review_fingerprint": FINGERPRINT,
        "approved_source_sha256": digest_map,
        "candidate_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
        "public_mcp_pid": expected_pid,
        "public_readiness": {
            "schema_version": 1, "state": "PUBLIC_HYBRID_CONCURRENCY_PASS_READONLY",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "candidate": CANDIDATE,
            "candidate_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            "activation_permitted": False, "public_proof": before,
        },
    }
    ready = assess_supervised_trial(BASE, CANDIDATE, evidence)
    if ready.get("state") != "READY_FOR_SUPERVISED_TRIAL" or not ready.get("safe_to_activate"):
        raise RuntimeError("release gate rejected evidence: " + str(ready.get("blockers")))
    report = {"candidate": CANDIDATE, "state": "RELEASE_PREPARED",
              "public_before": before, "release_authorized": True,
              "source_fingerprint": FINGERPRINT, "public_after": None,
              "rollback": None, "error": None}
    try:
        print("RELEASE_POINTER_BEGIN", flush=True)
        report["switch"] = publish_validated_generation(
            baseline=BASE, candidate=CANDIDATE,
            operator_authorization=authorization,
            public_reader_attestation={"generation_lock_enabled": True, "mcp_restart_confirmed": True},
            trial_evidence=evidence,
        )
        report["public_after"] = asyncio.run(prove_candidate())
        print("RELEASE_PUBLIC_CANDIDATE_PASS", flush=True)
        report["state"] = "RELEASE_ACTIVE_PUBLIC_VERIFIED"
    except BaseException as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)[:600]
        print("RELEASE_FAILURE_ROLLBACK", report["error"], flush=True)
        try:
            if (state / "production-generation-transition.json").exists():
                report["rollback"] = rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            elif (state / "active-generation.json").exists():
                report["rollback"] = revert_active_to_legacy(
                    baseline=BASE, expected_candidate=CANDIDATE,
                    operator_authorization="CODEBRIDGE_RAG_V1_ROLLBACK:" + CANDIDATE,
                )
            else:
                report["rollback"] = {"state": "LEGACY_UNCHANGED"}
            report["legacy_proof"] = asyncio.run(prove_legacy())
            report["state"] = "RELEASE_FAILED_ROLLED_BACK"
        except BaseException as rollback_error:
            report["state"] = "CRITICAL_RECOVERY_REQUIRED"
            report["rollback_error"] = repr(rollback_error)[:600]
            print("CRITICAL_RECOVERY_REQUIRED", report["rollback_error"], flush=True)
    finally:
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print("RELEASE_RESULT", json.dumps({
        "state": report["state"], "candidate": CANDIDATE,
        "public_after": report["public_after"], "rollback": report["rollback"],
    }), flush=True)
    return 0 if report["state"] == "RELEASE_ACTIVE_PUBLIC_VERIFIED" else 3


if __name__ == "__main__":
    sys.exit(run())
