"""Pure, fail-closed supervisor lifecycle contract; no process or scheduler runs.

The controller only models in-process transitions for isolated testing.
Cross-process single-instance enforcement must be implemented and tested separately.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class SupervisorState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SupervisorSnapshot:
    state: SupervisorState = SupervisorState.STOPPED
    generation: int = 0
    stop_requested: bool = False


def transition(
    snapshot: SupervisorSnapshot, event: str, *, expected_generation: int | None = None,
) -> tuple[SupervisorSnapshot, dict]:
    """Model a single atomic event; never start/kill a process or consume a job."""
    if not isinstance(snapshot, SupervisorSnapshot):
        raise TypeError("expected SupervisorSnapshot")
    old = snapshot.state
    event = str(event)
    # A delayed completion from a prior start must not modify the current
    # supervisor. Runner callbacks will be required to carry generation IDs.
    if event in ("started", "stopped", "failed"):
        if type(expected_generation) is not int or expected_generation != snapshot.generation:
            return snapshot, {
                "state": old.value, "accepted": False,
                "reason": "STALE_OR_MISSING_GENERATION",
                "worker_started": False, "safe_to_publish": False,
            }
    allowed = {
        (SupervisorState.STOPPED, "request_start"): SupervisorState.STARTING,
        (SupervisorState.STARTING, "started"): SupervisorState.RUNNING,
        (SupervisorState.STARTING, "request_stop"): SupervisorState.STOPPING,
        (SupervisorState.RUNNING, "request_stop"): SupervisorState.STOPPING,
        (SupervisorState.STOPPING, "stopped"): SupervisorState.STOPPED,
        (SupervisorState.STARTING, "failed"): SupervisorState.FAILED,
        (SupervisorState.RUNNING, "failed"): SupervisorState.FAILED,
        (SupervisorState.STOPPING, "failed"): SupervisorState.FAILED,
        (SupervisorState.FAILED, "reset"): SupervisorState.STOPPED,
    }
    destination = allowed.get((old, event))
    if destination is None:
        return snapshot, {
            "state": old.value, "accepted": False, "reason": "INVALID_TRANSITION",
            "worker_started": False, "safe_to_publish": False,
        }
    generation = snapshot.generation + int(event == "request_start")
    after = replace(
        snapshot, state=destination, generation=generation,
        stop_requested=(event == "request_stop" or (
            snapshot.stop_requested and destination == SupervisorState.STOPPING)),
    )
    if destination == SupervisorState.STOPPED:
        after = replace(after, stop_requested=False)
    return after, {
        "state": after.state.value, "accepted": True,
        "worker_started": False, "safe_to_publish": False,
    }
