"""RAG-DEL DQ-E-F-1: validate externally observed, read-only live MCP probe.

No imports from MCP, no network and no mutations. Caller supplies observed
list_tools and call_tool evidence; this function is NOT an operational gate.
"""
from __future__ import annotations


_REQUIRED = ("search", "context", "status")


def review_live_generation_probe_dev(
    tool_names: list[str], probe: dict, *, read_only_hint: bool,
    expected_pid: int | None = None,
) -> dict:
    """Fail closed on missing tools, mismatched PID or malformed probe."""
    if not isinstance(tool_names, list) or any(
        not isinstance(x, str) for x in tool_names
    ):
        raise ValueError("invalid MCP tool listing")
    if not isinstance(probe, dict) or type(read_only_hint) is not bool:
        raise ValueError("invalid MCP probe evidence")
    if expected_pid is not None and (
        type(expected_pid) is not int or expected_pid <= 0
    ):
        raise ValueError("invalid expected PID")

    details = probe.get("details")
    if not isinstance(details, dict):
        details = {}
    readers = details.get("loaded_reader_functions")
    if not isinstance(readers, dict):
        readers = {}
    pid = details.get("mcp_pid")
    generation = details.get("generation")
    checks = {
        "tool_listed": "codebridge_rag_generation_probe" in tool_names,
        "tool_declared_read_only": read_only_hint,
        "probe_success": probe.get("operation_ok") is True
                         and probe.get("state") == "PUBLIC_READER_PROBE_PASS",
        "reader_functions_loaded": all(
            readers.get(name) is True for name in _REQUIRED
        ),
        "reader_generation_lock": details.get("writer_blocked_during_read") is True,
        "semantic_serialization": details.get(
            "semantic_worker_serialization_loaded"
        ) is True,
        "runtime_generation_present": isinstance(generation, str)
                                      and len(generation) > 0,
        "runtime_pid_valid": type(pid) is int and pid > 0,
        "pid_matches_observed_listener": (
            expected_pid is None or pid == expected_pid
        ),
        "probe_does_not_authorize": (
            probe.get("safe_to_activate") is False
            and details.get("safe_to_activate") is False
        ),
    }
    blockers = [key for key, passed in checks.items() if not passed]
    return {
        "state": (
            "LIVE_MCP_READERS_OBSERVED_READ_ONLY" if not blockers
            else "LIVE_MCP_ATTESTATION_BLOCKED"
        ),
        "checks": checks,
        "blockers": blockers,
        "runtime_pid": pid if type(pid) is int and pid > 0 else None,
        "runtime_generation": generation if isinstance(generation, str) else None,
        "tool_count": len(tool_names),
        "live_mcp_probe_attested": not blockers,
        "child_semantic_execution_attested": False,
        "gui_loaded_reader_attested": False,
        "queue_barrier_held": False,
        "ready_for_operational_pilot": False,
        "activation_authorized": False,
        "operational_use_allowed": False,
        "read_only": True,
    }