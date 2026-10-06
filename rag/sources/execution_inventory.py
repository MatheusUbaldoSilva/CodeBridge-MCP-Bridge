"""Execution and audit source contract for RAG-002-D.

The ledger remains the source of truth.
This module only projects approved execution metadata into a RAG-safe shape.
It never reads RAW output, opens the ledger, executes commands, or indexes data.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


INDEXABLE_EXECUTION_FIELDS = frozenset({
    "execution_id",
    "target",
    "command_hash",
    "state",
    "exit_code",
    "error_type",
    "error_message",
    "started_at",
    "finished_at",
})

SUMMARY_METADATA_FIELDS = frozenset({
    "duration_ms",
    "output_mode",
    "compaction_applied",
    "stdout_lines",
    "stderr_lines",
    "stdout_chars",
    "stderr_chars",
    "returned_stdout_chars",
})

FORBIDDEN_EXECUTION_CONTENT_FIELDS = frozenset({
    "output",
    "stdout",
    "stderr",
    "text",
    "stdout_delta",
    "stderr_delta",
    "failed_command",
    "important_sections",
    "execution_output_chunks",
    "raw",
    "raw_output",
})


def _required_text(row: Mapping[str, Any], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _summary_metadata(summary: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if summary is None:
        return {}
    if not isinstance(summary, Mapping):
        raise ValueError("summary must be a mapping")

    forbidden = FORBIDDEN_EXECUTION_CONTENT_FIELDS.intersection(summary)
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(f"summary contains forbidden RAW-derived fields: {names}")

    return {
        key: summary[key]
        for key in SUMMARY_METADATA_FIELDS
        if key in summary
    }


def build_execution_index_record(
    ledger_row: Mapping[str, Any],
    *,
    summary: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the metadata-only record permitted by RAG-002-D.

    RAW output is represented only by an execution_id reference.
    The function intentionally excludes output text and failed_command.
    """

    if not isinstance(ledger_row, Mapping):
        raise ValueError("ledger_row must be a mapping")

    forbidden = FORBIDDEN_EXECUTION_CONTENT_FIELDS.intersection(ledger_row)
    # Presence in the ledger is expected; it is excluded rather than copied.
    # This variable makes the exclusion deliberate and testable.
    _ = forbidden

    execution_id = _required_text(ledger_row, "execution_id")
    target = _required_text(ledger_row, "target")
    command_hash = _required_text(ledger_row, "command_hash")
    state = _required_text(ledger_row, "state").upper()

    error_type = ledger_row.get("error_type")
    error_message = ledger_row.get("error_message")
    exit_code = ledger_row.get("exit_code")

    structured_error = None
    if error_type is not None or error_message is not None or exit_code not in (None, 0):
        structured_error = {
            "error_type": error_type,
            "error_message": error_message,
            "exit_code": exit_code,
        }

    record = {
        "execution_id": execution_id,
        "target": target,
        "command_hash": command_hash,
        "status": state,
        "structured_error": structured_error,
        "summary": {
            "started_at": ledger_row.get("started_at"),
            "finished_at": ledger_row.get("finished_at"),
            **_summary_metadata(summary),
        },
        "raw_reference": {
            "execution_id": execution_id,
            "raw_available": True,
        },
    }
    return record
