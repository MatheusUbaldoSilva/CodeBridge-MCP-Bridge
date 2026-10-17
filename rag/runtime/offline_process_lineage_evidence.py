"""Temporal parent-child evidence for scoped synthetic Windows CIM snapshots.

No real shutdown or copy permission is granted by this module.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from rag.runtime.offline_process_sample_contract import validate_observation_series
from rag.runtime.offline_process_family_supervisor import inspect_family_shutdown_samples

def _birth_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid birth timestamp")
    match = re.fullmatch(r"/Date\((\d+)(?:[+-]\d{4})?\)/", value)
    if match:
        return datetime.fromtimestamp(int(match.group(1))/1000, timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("naive birth timestamp")
    return parsed.astimezone(timezone.utc)

def assess_scoped_family_timeline(root_pid, samples):
    report = {"state": "BLOCKED", "issues": [], "known_family_pids": [],
              "copy_authorized": False, "production_quiescence_proven": False,
              "all_handles_closed": False}
    try:
        contract = validate_observation_series(samples)
        if contract["state"] != "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN":
            report["issues"].append("INVALID_TIMED_SAMPLE_SERIES")
            return report
        if type(root_pid) is not int or root_pid <= 0:
            raise ValueError("invalid root")
        first = {row["pid"]: row for row in samples[0]["verified_pids"]}
        if root_pid not in first:
            report["issues"].append("ROOT_NOT_OBSERVED")
            return report
        baseline = dict(first)
        identities = {}
        parents = {}
        for sample in samples:
            for row in sample["verified_pids"]:
                pid = row["pid"]
                birth = _birth_timestamp(row["created_at"])
                identity = (birth, row["executable_fingerprint"])
                if pid in identities and identities[pid] != identity:
                    report["issues"].append("PID_REUSED_OR_IDENTITY_CHANGED")
                    return report
                identities[pid] = identity
                if pid in parents and parents[pid] != row["parent_pid"]:
                    report["issues"].append("PROCESS_REPARENTED_OR_PPID_CHANGED")
                    return report
                parents[pid] = row["parent_pid"]
                if birth > datetime.fromisoformat(sample["observed_end_utc"]).astimezone(timezone.utc):
                    report["issues"].append("PROCESS_BORN_AFTER_OBSERVATION")
                    return report
        for pid, row in baseline.items():
            if pid == root_pid:
                continue
            parent = row["parent_pid"]
            if parent not in baseline:
                report["issues"].append("UNVERIFIED_PARENT_IN_BASELINE")
                return report
            if identities[pid][0] < identities[parent][0]:
                report["issues"].append("CHILD_PREDATES_PARENT")
                return report
        family = inspect_family_shutdown_samples(root_pid, samples)
        if family["state"] != "LAB_FAMILY_ABSENT_UNPROVEN":
            report["issues"].append("FAMILY_EXIT_UNPROVEN")
            return report
        report["known_family_pids"] = family["observed_family_pids"]
        if set(report["known_family_pids"]) != set(baseline):
            report["issues"].append("UNEXPECTED_BASELINE_MEMBERS")
            report["known_family_pids"] = []
            return report
        report["state"] = "LAB_TEMPORAL_FAMILY_EXIT_UNPROVEN_FOR_PRODUCTION"
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        report["issues"].append(type(exc).__name__)
    return report
