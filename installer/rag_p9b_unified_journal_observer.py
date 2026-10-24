"""P9-B read-only combined recovery journal projection (never grants update)."""
from __future__ import annotations
import json
import re
from pathlib import Path
from installer.rag_p9b_rollback_journal import read_journal, _strict_journal_pairs

SHA256 = re.compile(r"^[0-9a-f]{64}$")
ORDER = (
    "SHELL_DETACHED_COMBINED_ARMED",
    "SHELL_DETACHED_FILES_VERIFIED",
    "SHELL_DETACHED_SHELL_VERIFIED",
    "SHELL_DETACHED_COMBINED_VERIFIED",
)


def observe_combined_transaction(path, *, expected_transaction_sha256):
    denied = {"state": "P9B_UNIFIED_REVIEW_REQUIRED", "verified": False,
              "read_only": True, "production_modified": False,
              "cutover_authorized": False}
    if (not isinstance(expected_transaction_sha256, str)
            or SHA256.fullmatch(expected_transaction_sha256) is None):
        return {**denied, "reason": "TRANSACTION_IDENTITY_REQUIRED"}
    current = read_journal(path)
    if current.get("state") != "JOURNAL_OBSERVED_ONLY" or current.get("count", 0) < 1:
        return {**denied, "reason": "JOURNAL_UNVERIFIED"}
    try:
        entries = [json.loads(line, object_pairs_hook=_strict_journal_pairs)
                   for line in Path(path).read_text(encoding="utf-8").splitlines()]
        if entries[0].get("state") != ORDER[0]:
            return {**denied, "reason": "WRONG_INITIAL_EVENT"}
        identity = entries[0].get("details", {}).get("transaction_sha256")
        if identity != expected_transaction_sha256:
            return {**denied, "reason": "TRANSACTION_IDENTITY_MISMATCH"}
        positions = {name: [] for name in ORDER}
        for i, item in enumerate(entries):
            if not isinstance(item, dict):
                return {**denied, "reason": "JOURNAL_SCHEMA_INVALID"}
            state = item.get("state")
            if state in positions:
                positions[state].append(i)
                if state != ORDER[0] and item.get("details", {}).get("postverified") is not True:
                    return {**denied, "reason": "POSTVERIFY_PROOF_MISSING"}
        if any(len(positions[state]) > 1 for state in ORDER):
            return {**denied, "reason": "DUPLICATE_PHASE_EVENT"}
        if any(len(positions[state]) == 0 for state in ORDER):
            return {**denied, "reason": "TRANSACTION_INCOMPLETE",
                    "observed": [state for state in ORDER if positions[state]]}
        if [positions[state][0] for state in ORDER] != sorted(
                positions[state][0] for state in ORDER):
            return {**denied, "reason": "PHASE_ORDER_INVALID"}
        if positions[ORDER[-1]][0] != len(entries)-1:
            return {**denied, "reason": "EVENT_AFTER_TERMINAL"}
        if any(any(marker in e["state"] for marker in ("FAILED", "EXCEPTION", "UNVERIFIED", "REFUSED")) for e in entries):
            return {**denied, "reason": "FAILURE_IN_JOURNAL"}
        return {**denied, "state": "P9B_COMBINED_JOURNAL_OBSERVED_COMPLETE",
                "verified": True, "events": len(entries),
                "transaction_sha256": expected_transaction_sha256}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {**denied, "reason": "JOURNAL_INSPECTION_FAILED"}