"""Conservative coverage report for synthetic RAG laboratory evidence only."""
from __future__ import annotations

def summarize_lab_coverage(catalog, handles, *, observed_handles=(), released_handles=(), unknown=()):
    checked = list(catalog.get("files", [])) if isinstance(catalog, dict) else []
    observed = list(observed_handles)
    released = list(released_handles)
    omitted = list(unknown)
    missing = sorted(set(observed) - set(released))
    issues = []
    if not checked:
        issues.append("CATALOG_NOT_VERIFIED")
    if not isinstance(handles, dict) or handles.get("state") != "LAB_HANDLES_READABLE_UNPROVEN":
        issues.append("HANDLE_PROBE_NOT_CLEAR")
    if missing:
        issues.append("OBSERVED_HANDLES_NOT_RELEASED")
    if omitted:
        issues.append("UNKNOWN_OBJECTS_PRESENT")
    issues.append("GLOBAL_WINDOWS_HANDLES_AND_MAPPINGS_UNOBSERVABLE")
    return {
        "state": "LAB_COVERAGE_INCOMPLETE",
        "verified_file_paths": sorted(checked),
        "observed_handles": sorted(observed),
        "released_handles": sorted(released),
        "unreleased_handles": missing,
        "unknown_objects": sorted(omitted),
        "unobservable_groups": ["OTHER_PROCESSES", "FILE_MAPPINGS", "KERNEL_HANDLES", "UNSCOPED_CONSUMERS"],
        "issues": issues,
        "copy_authorized": False,
        "all_handles_closed": False,
        "production_quiescence_proven": False,
    }
