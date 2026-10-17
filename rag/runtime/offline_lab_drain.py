"""Deterministic synthetic-only drain gate, independent from real MCP."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class LabDrain:
    active: int = 0
    state: str = "ACCEPTING"
    def __post_init__(self):
        if type(self.active) is not int or self.active < 0:
            raise ValueError("invalid active count")
    def start(self):
        if self.state != "ACCEPTING":
            return False
        self.active += 1
        return True
    def finish(self):
        if self.active < 1:
            raise ValueError("no active work")
        self.active -= 1
        if self.state == "DRAINING" and self.active == 0:
            self.state = "DRAINED"
    def request_drain(self):
        if self.state != "ACCEPTING":
            return False
        self.state = "DRAINED" if self.active == 0 else "DRAINING"
        return True
    def timeout(self):
        if self.state != "DRAINING":
            return False
        self.state = "BLOCKED_TIMEOUT"
        return True
    def abort(self):
        if self.state not in ("DRAINING","DRAINED","BLOCKED_TIMEOUT"):
            return False
        self.state = "ACCEPTING"
        return True
    def report(self):
        return {"state": self.state, "active": self.active,
                "drain_ack": self.state == "DRAINED",
                "new_requests_allowed": self.state == "ACCEPTING",
                "copy_authorized": False, "production_quiescence_proven": False}
