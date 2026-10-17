"""Synthetic dependency-aware shutdown contract; no real process actions."""
from __future__ import annotations

ORDER = ("gui", "mcp", "adapter", "indexer")

def simulate_dependent_shutdown(*, active=(), late_children=(), restart_attempts=(),
                                 failed_services=(), reconnect_attempts=()):
    known = set(ORDER)
    sets = (active, late_children, restart_attempts, failed_services, reconnect_attempts)
    if any(not isinstance(values, (tuple, list, set, frozenset)) or
           any(not isinstance(item,str) or not item for item in values)
           for values in sets):
        raise ValueError("invalid synthetic scenario")
    if any(item not in known for item in active):
        raise ValueError("unknown primary service")
    state = {name: name in active for name in ORDER}
    issues = []
    stopped = []
    for name in ORDER:
        if name in failed_services and state[name]:
            issues.append("STOP_FAILED:" + name)
            continue
        if state[name]:
            stopped.append(name)
            state[name] = False
        if name in late_children:
            issues.append("LATE_CHILD:" + name)
        if name in restart_attempts:
            issues.append("RESTART_ATTEMPT:" + name)
        if name in reconnect_attempts:
            issues.append("RECONNECT_ATTEMPT:" + name)
    if any(state.values()):
        issues.append("PRIMARY_STILL_ACTIVE")
    return {
        "state": "LAB_ORDER_OBSERVED_UNPROVEN" if not issues else "BLOCKED",
        "stop_order": stopped, "issues": issues,
        "copy_authorized": False, "all_handles_closed": False,
        "production_quiescence_proven": False,
    }
