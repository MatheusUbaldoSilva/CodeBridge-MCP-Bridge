"""Read-only installed MCP indexing readiness report. Never publish or activate."""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path


def summarize(probe: dict, integrity: dict, preview: dict) -> dict:
    observed = integrity.get("details") or {}
    plan = preview.get("plan") or {}
    delta = plan.get("incremental_preview") or {}
    gate = delta.get("publication_gate") or {}
    details = probe.get("details") or {}
    loaded = details.get("loaded_reader_functions") or {}
    reader = {
        "public_server_pid": details.get("mcp_pid"),
        "generation": details.get("generation"),
        "reader_pin_proved": probe.get("state") == "PUBLIC_READER_PROBE_PASS",
        "semantic_worker_serialization_loaded": details.get(
            "semantic_worker_serialization_loaded", False),
        "public_runtime_ready_for_hybrid_acceptance": (
            probe.get("operation_ok") is True
            and probe.get("state") == "PUBLIC_READER_PROBE_PASS"
            and all(loaded.get(k) is True for k in ("search", "context", "status"))
            and details.get("writer_blocked_during_read") is True
            and details.get("semantic_worker_serialization_loaded") is True
            and details.get("generation") == "legacy"
        ),
    }
    blockers = list(gate.get("reasons") or [])
    if not reader["public_runtime_ready_for_hybrid_acceptance"]:
        blockers.append("PUBLIC_READER_RUNTIME_NOT_ATTESTED")
    if (integrity.get("operation_ok") is not True or
        observed.get("state") != "OBSERVED_CONSISTENT"):
        blockers.append("PUBLIC_CROSSSTORE_INTEGRITY_NOT_ATTESTED")
    if (preview.get("operation_ok") is not True or
        preview.get("executed") is not False or
        preview.get("action") != "PLAN"):
        blockers.append("DRY_RUN_NOT_CONFIRMED")
    return {
        "state": "GO_LIVE_BLOCKED",
        "read_only": True,
        "executed": False,
        "safe_to_publish": False,
        "activation_authorized": False,
        "public_reader": reader,
        "public_integrity": {
            "state": observed.get("state"),
            "generation": observed.get("audited_generation"),
            "documents": observed.get("documents"),
            "chunks": observed.get("chunks"),
        },
        "candidate_count": plan.get("candidate_count"),
        "incremental_new_count": delta.get("new_count"),
        "review_status": plan.get("review_status"),
        "blockers": sorted(set(blockers)),
    }


async def audit(root: str, path: str) -> dict:
    from v1_public_readiness import _call
    probe = await _call("codebridge_rag_generation_probe", {})
    integrity = await _call("codebridge_rag_integrity", {})
    preview = await _call("codebridge_rag_index", {
        "project_id": "codebridge", "project_root": root,
        "scope": "CODE", "paths": [path], "execute": False,
    })
    return summarize(probe, integrity, preview)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    if not Path(args.root).is_dir() or not args.path.endswith(".py"):
        parser.error("valid project root and explicit Python source are required")
    try:
        report = asyncio.run(audit(args.root, args.path))
    except Exception as exc:
        report = {"state": "GO_LIVE_BLOCKED", "read_only": True,
                  "safe_to_publish": False, "activation_authorized": False,
                  "error_type": type(exc).__name__, "blockers": ["MCP_AUDIT_FAILED"]}
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if "error_type" not in report else 2


if __name__ == "__main__":
    raise SystemExit(main())
