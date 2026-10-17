"""Validation contract for externally timestamped synthetic process observations.

This is an evidence-format check only, never a production quiescence proof.
"""
from __future__ import annotations

from datetime import datetime, timezone

def validate_observation_series(samples, *, minimum=3):
    result = {
        "state": "BLOCKED", "issues": [], "samples_valid": 0,
        "source": None, "copy_authorized": False,
        "production_quiescence_proven": False, "all_handles_closed": False,
    }
    try:
        if not isinstance(samples, list) or len(samples) < minimum:
            raise ValueError("not enough samples")
        source = None
        last_end = None
        for sample in samples:
            if not isinstance(sample, dict):
                raise ValueError("invalid sample")
            if sample.get("identity_inventory_ok") is not True or sample.get("unverified_count") != 0:
                raise ValueError("untrusted inventory")
            if not isinstance(sample.get("verified_pids"), list):
                raise ValueError("invalid identities list")
            if sample.get("source") != "WINDOWS_CIM_LAB_SCOPED":
                raise ValueError("untrusted observation source")
            scope = sample.get("scope_pids")
            if not isinstance(scope, list) or not scope or any(
                type(pid) is not int or pid <= 0 for pid in scope
            ) or len(set(scope)) != len(scope):
                raise ValueError("invalid scoped PID set")
            expected_scope = tuple(sorted(scope))
            if source is None:
                source = expected_scope
            if expected_scope != source:
                raise ValueError("scope changed between observations")
            start = datetime.fromisoformat(sample["observed_start_utc"])
            end = datetime.fromisoformat(sample["observed_end_utc"])
            if start.tzinfo is None or end.tzinfo is None:
                raise ValueError("naive observation clock")
            start = start.astimezone(timezone.utc)
            end = end.astimezone(timezone.utc)
            if end < start:
                raise ValueError("observation end before start")
            if last_end is not None and start < last_end:
                raise ValueError("overlapping or reversed observations")
            last_end = end
            seen = set()
            for entry in sample["verified_pids"]:
                if not isinstance(entry, dict):
                    raise ValueError("invalid process row")
                pid = entry.get("pid")
                ppid = entry.get("parent_pid")
                born = entry.get("created_at")
                fingerprint = entry.get("executable_fingerprint")
                if (type(pid) is not int or pid not in source or pid in seen
                        or type(ppid) is not int or ppid < 0
                        or not isinstance(born, str) or not born
                        or not isinstance(fingerprint, str)
                        or len(fingerprint) != 64
                        or any(c not in "0123456789abcdef" for c in fingerprint)):
                    raise ValueError("unscoped or incomplete process identity")
                seen.add(pid)
            result["samples_valid"] += 1
        result["source"] = "WINDOWS_CIM_LAB_SCOPED"
        result["state"] = "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN"
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        result["issues"].append(type(exc).__name__)
    return result
