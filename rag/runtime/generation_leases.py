"""In-process generation reader leases (test-only lifecycle prototype).

No filesystem deletion is implemented here. Cross-process leases and crash
recovery are required before enabling production generation garbage collection.
"""
from __future__ import annotations
from contextlib import contextmanager
from threading import RLock
from rag.runtime.generation_read_session import pin_generation_for_read


class GenerationLeaseRegistry:
    def __init__(self):
        self._lock = RLock()
        self._counts = {}

    @contextmanager
    def acquire(self, state_root):
        with self._lock:
            session = pin_generation_for_read(state_root)
            self._counts[session.name] = self._counts.get(session.name, 0) + 1
        try:
            yield session
        finally:
            with self._lock:
                remaining = self._counts[session.name] - 1
                if remaining:
                    self._counts[session.name] = remaining
                else:
                    del self._counts[session.name]

    def has_readers(self, name):
        with self._lock:
            return self._counts.get(name, 0) > 0

    def can_retire(self, name, active_name):
        with self._lock:
            return name != active_name and self._counts.get(name, 0) == 0

    def snapshot(self):
        with self._lock:
            return dict(self._counts)
