"""Fail-closed sampling-window evidence for known synthetic Windows PID scopes.

Never claims system-wide process discovery, handle release, or production backup.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from rag.runtime.offline_process_sample_contract import validate_observation_series


def evaluate_scoped_exit_window(samples, *, now=None, max_span_ms=2500,
                                max_gap_ms=3500, max_age_ms=8500):
    report = {
        "state": "BLOCKED", "issues": [], "samples_verified": 0,
        "observed_live_pids": [], "observed_absent_pids": [],
        "copy_authorized": False, "all_handles_closed": False,
        "production_quiescence_proven": False,
    }
    try:
        if any(type(value) is not int or value < 1
               for value in (max_span_ms, max_gap_ms, max_age_ms)):
            raise ValueError("invalid window limits")
        contract = validate_observation_series(samples)
        if contract["state"] != "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN":
            report["issues"].append("INVALID_OBSERVATIONS")
            return report
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("trusted evaluation clock required")
        now_utc = now.astimezone(timezone.utc)
        observed = set()
        identities = {}
        absent = set()
        scope = set(samples[0]["scope_pids"])
        last_end = None
        consecutive_empty = 0
        for sample in samples:
            start = datetime.fromisoformat(sample["observed_start_utc"]).astimezone(timezone.utc)
            end = datetime.fromisoformat(sample["observed_end_utc"]).astimezone(timezone.utc)
            if (end-start) > timedelta(milliseconds=max_span_ms):
                report["issues"].append("OBSERVATION_TIMEOUT")
                return report
            if last_end is not None and (start-last_end) > timedelta(milliseconds=max_gap_ms):
                report["issues"].append("OBSERVATION_GAP_EXCEEDED")
                return report
            if end > now_utc:
                report["issues"].append("OBSERVATION_FROM_FUTURE")
                return report
            last_end = end
            active = set()
            for row in sample["verified_pids"]:
                pid = row["pid"]
                fingerprint = (row["created_at"], row["executable_fingerprint"])
                if pid in identities and identities[pid] != fingerprint:
                    report["issues"].append("PID_IDENTITY_CHANGED")
                    return report
                if pid in absent:
                    report["issues"].append("PID_REAPPEARED")
                    return report
                identities[pid] = fingerprint
                active.add(pid)
            observed.update(active)
            absent.update(scope-active)
            consecutive_empty = consecutive_empty+1 if not active else 0
            report["samples_verified"] += 1
        report["observed_live_pids"] = sorted(observed)
        report["observed_absent_pids"] = sorted(absent)
        if (now_utc-last_end) > timedelta(milliseconds=max_age_ms):
            report["issues"].append("STALE_FINAL_OBSERVATION")
        if observed != scope:
            report["issues"].append("EXPECTED_PID_NEVER_OBSERVED")
        if consecutive_empty < 2:
            report["issues"].append("TWO_CONSECUTIVE_ABSENCES_REQUIRED")
        if not report["issues"]:
            report["state"] = "LAB_SCOPED_EXIT_WINDOW_UNPROVEN"
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        report["issues"].append(type(exc).__name__)
    return report
