"""One-shot, explicitly invoked supervisor laboratory runner.

Runs only a supplied, inert callback while holding an OS lock. Never calls a
RAG worker, changes persistent scheduler settings or publishes an index.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from rag.runtime.incremental_supervisor_lifecycle import (
    SupervisorSnapshot, SupervisorState, transition,
)
from rag.runtime.incremental_supervisor_lock import SupervisorLock


@dataclass
class SupervisorLabRunner:
    lock_path: Path
    snapshot: SupervisorSnapshot = field(default_factory=SupervisorSnapshot)

    def run_once(self, callback: Callable[[], None] | None = None) -> dict:
        if self.snapshot.state != SupervisorState.STOPPED:
            return self._report("ALREADY_ACTIVE_OR_FAILED")
        if callback is None or not callable(callback):
            return self._report("NO_LAB_CALLBACK")
        lock = SupervisorLock(self.lock_path)
        if not lock.acquire():
            return self._report("LOCK_UNAVAILABLE")
        try:
            self.snapshot, started = transition(self.snapshot, "request_start")
            if not started["accepted"]:
                return self._report("START_DENIED")
            gen = self.snapshot.generation
            self.snapshot, confirmed = transition(
                self.snapshot, "started", expected_generation=gen)
            if not confirmed["accepted"]:
                return self._report("START_CONFIRMATION_DENIED")
            try:
                callback()
            except Exception:
                self.snapshot, _ = transition(
                    self.snapshot, "failed", expected_generation=gen)
                return self._report("LAB_CALLBACK_FAILED")
            self.snapshot, _ = transition(self.snapshot, "request_stop")
            self.snapshot, _ = transition(
                self.snapshot, "stopped", expected_generation=gen)
            return self._report("LAB_CYCLE_COMPLETE")
        finally:
            lock.release()

    def reset_after_failure(self) -> bool:
        if self.snapshot.state != SupervisorState.FAILED:
            return False
        self.snapshot, result = transition(self.snapshot, "reset")
        return result["accepted"]

    def _report(self, state: str) -> dict:
        return {
            "state": state, "supervisor_state": self.snapshot.state.value,
            "generation": self.snapshot.generation,
            "worker_started": False, "scheduler_started": False,
            "active_index_updated": False, "safe_to_publish": False,
        }
