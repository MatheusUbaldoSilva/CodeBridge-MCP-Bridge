"""DQ-E-F-3: aggregate DEV read-only evidence without authorizing operations."""
from __future__ import annotations

def review_deletion_readiness_evidence_dev(
    mcp: dict, supervisor: dict, journal: dict, *,
    gui_runtime_attested: bool=False,
    semantic_child_attested: bool=False,
) -> dict:
    """Caller inputs are observations, never runtime authority or activation tokens."""
    if any(not isinstance(x,dict) for x in (mcp,supervisor,journal)):
        raise ValueError("missing evidence")
    if type(gui_runtime_attested) is not bool or type(semantic_child_attested) is not bool:
        raise ValueError("attestation values must be bool")
    checks={
        "mcp_readonly_loaded":mcp.get("live_mcp_probe_attested") is True
             and mcp.get("read_only") is True and mcp.get("activation_authorized") is False,
        "supervisor_queue_clean":supervisor.get("state")=="SUPERVISOR_REVIEW_BLOCKED_READ_ONLY"
             and supervisor.get("supervisor_observed_quiet") is True
             and not supervisor.get("blockers") and supervisor.get("read_only") is True,
        "queue_barrier_held":supervisor.get("queue_barrier_held") is True,
        "journals_readonly_clean":journal.get("state")=="DELETION_JOURNAL_INVENTORY_READ_ONLY_CLEAN"
             and journal.get("read_only") is True and journal.get("activation_authorized") is False,
        "gui_runtime_attested":gui_runtime_attested,
        "semantic_child_attested":semantic_child_attested,
    }
    missing=[name for name,observed in checks.items() if not observed]
    return dict(
        state="DELETION_EVIDENCE_BLOCKED" if missing else "EVIDENCE_REVIEW_ONLY",
        checks=checks,blockers=missing,ready_for_operational_pilot=False,
        queue_barrier_acquired_by_this_review=False,activation_authorized=False,
        operational_use_allowed=False,read_only=True,
    )
