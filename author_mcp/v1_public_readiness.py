"""Read-only public MCP V1.03-C probe and optional concurrent HYBRID acceptance.

This script never activates an index, mutates a generation, or restarts MCP.
Run using the author MCP Python environment after an operator-led GUI reload.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import httpx2 as httpx
from mcp.client.streamable_http import streamable_http_client


_ENDPOINT = "http://127.0.0.1:8765/mcp"
_QUERY = "CodeBridge RAG incremental source hashes"


async def _call(tool: str, args: dict) -> dict:
    # Jina workers intentionally serialize for Qdrant Local. The third
    # concurrent request can outlive the default HTTP read timeout even when
    # the queue is healthy. Bound the outer proof above the 100s queue +
    # 180s inference watchdog rather than reporting false failures.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(330.0, connect=10.0),
    ) as transport:
        async with streamable_http_client(
            _ENDPOINT, http_client=transport,
        ) as (reader, writer):
            async with ClientSession(
                reader, writer, read_timeout_seconds=330.0,
            ) as client:
                await client.initialize()
                response = await client.call_tool(tool, args)
                payload = response.structured_content
                if response.is_error or not isinstance(payload, dict):
                    raise RuntimeError(tool + " did not return structured success")
                return payload


def _inspect_probe(probe: dict) -> dict:
    details = probe.get("details") or {}
    readers = details.get("loaded_reader_functions") or {}
    ready = (
        probe.get("operation_ok") is True
        and probe.get("state") == "PUBLIC_READER_PROBE_PASS"
        and all(readers.get(name) is True for name in ("search", "context", "status"))
        and details.get("writer_blocked_during_read") is True
        and details.get("semantic_worker_serialization_loaded") is True
        and details.get("generation") == "legacy"
    )
    return {
        "public_server_pid": details.get("mcp_pid"),
        "generation": details.get("generation"),
        "reader_pin_proved": probe.get("state") == "PUBLIC_READER_PROBE_PASS",
        "semantic_worker_serialization_loaded": details.get(
            "semantic_worker_serialization_loaded", False
        ),
        "public_runtime_ready_for_hybrid_acceptance": ready,
    }


async def _audit(concurrent: bool) -> dict:
    probe = await _call("codebridge_rag_generation_probe", {})
    info = _inspect_probe(probe)
    report: dict = {
        "check": "CODEBRIDGE_RAG_V103_PUBLIC_READONLY",
        "state": "BLOCKED",
        "public_reader": info,
        "safe_to_activate": False,
        "index_pointer_updated": False,
    }
    if not info["public_runtime_ready_for_hybrid_acceptance"]:
        report["reason"] = "PUBLIC_MCP_RELOAD_OR_SEMANTIC_LOCK_NOT_ATTESTED"
        return report

    status = await _call("codebridge_rag_status", {})
    index = status.get("index") or {}
    projects = status.get("projects") or []
    if (index.get("state") != "READY" or index.get("generation") != "legacy"
            or not projects or projects[0].get("document_count") != 210
            or projects[0].get("chunk_count") != 8761):
        report["reason"] = "PUBLIC_INDEX_BASELINE_MISMATCH"
        return report
    report["status"] = {
        "generation": index["generation"],
        "documents": projects[0]["document_count"],
        "chunks": projects[0]["chunk_count"],
    }
    # The public process must also prove SQLite, manifest and both Qdrant
    # local collections consistent before we subject it to concurrent load.
    integrity = await _call("codebridge_rag_integrity", {})
    observed = integrity.get("details") or {}
    if (
        integrity.get("operation_ok") is not True
        or observed.get("state") != "OBSERVED_CONSISTENT"
        or observed.get("audited_generation") != "legacy"
        or observed.get("documents") != 210
        or observed.get("chunks") != 8761
        or observed.get("manifest_entries") != 210
    ):
        report["reason"] = "PUBLIC_CROSSSTORE_INTEGRITY_NOT_VERIFIED"
        return report
    report["cross_store_integrity"] = {
        "state": observed["state"],
        "generation": observed["audited_generation"],
        "documents": observed["documents"],
        "chunks": observed["chunks"],
    }
    if not concurrent:
        report["state"] = "READY_FOR_CONCURRENT_READONLY_TEST"
        return report

    results = await asyncio.gather(
        *(_call("codebridge_search_context", {
            "query": _QUERY,
            "project": "codebridge",
            "source_types": ["DOCUMENTATION", "CODE"],
            "top_k": 3,
        }) for _ in range(3)),
        return_exceptions=True,
    )
    checks = []
    for i, result in enumerate(results, 1):
        if isinstance(result, BaseException):
            checks.append({"request": i, "ok": False, "error": str(result)[:180]})
            continue
        passed = (
            result.get("operation_ok") is True
            and result.get("effective_route") == "HYBRID"
            and result.get("fallback_reason") is None
            and result.get("result_count") == 3
        )
        checks.append({"request": i, "ok": passed,
                       "route": result.get("effective_route"),
                       "results": result.get("result_count"),
                       "error_type": result.get("operation_error_type")})
    report["hybrid_concurrent"] = checks
    if all(item["ok"] for item in checks):
        report["state"] = "PUBLIC_HYBRID_CONCURRENCY_PASS"
    else:
        report["reason"] = "PUBLIC_HYBRID_CONCURRENCY_FAILED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrent", action="store_true",
                        help="After the public process probe passes, run 3 parallel HYBRID queries.")
    args = parser.parse_args()
    try:
        result = asyncio.run(_audit(args.concurrent))
    except Exception as exc:
        result = {
            "check": "CODEBRIDGE_RAG_V103_PUBLIC_READONLY",
            "state": "BLOCKED", "error": type(exc).__name__,
            "reason": str(exc)[:300], "safe_to_activate": False,
        }
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if result["state"] in (
        "READY_FOR_CONCURRENT_READONLY_TEST", "PUBLIC_HYBRID_CONCURRENCY_PASS"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
