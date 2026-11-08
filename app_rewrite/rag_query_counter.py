"""Contador de consultas ao RAG feitas enquanto o CodeBridge esta aberto.

Fica so em memoria: comeca em zero quando o app abre e some quando ele fecha.
Cada consulta soma no total da sessao e, se houver um ciclo do cronometro em
andamento, tambem no ciclo (identificado pelo request_id do cronometro). Um
ciclo novo comeca do zero.
"""
from __future__ import annotations

import threading
import time

SOURCES = ("MCP", "TELA", "IA_LOCAL")  # IA_LOCAL: consultas da aba IA Local


def _source(value):
    value = str(value or "MCP").strip().upper()
    return value if value in SOURCES else "MCP"


class RagQueryCounter:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.RLock()
        self.opened_at = clock()
        self._session = {s: 0 for s in SOURCES}
        self._cycle_key = None
        self._cycle = {s: 0 for s in SOURCES}
        self._last_at = None

    def record(self, source="MCP", cycle_key=None):
        source = _source(source)
        cycle_key = str(cycle_key or "").strip() or None
        with self._lock:
            self._session[source] += 1
            if cycle_key:
                if cycle_key != self._cycle_key:
                    self._cycle_key = cycle_key
                    self._cycle = {s: 0 for s in SOURCES}
                self._cycle[source] += 1
            self._last_at = self._clock()
            return self._snapshot_locked(cycle_key)

    def snapshot(self, cycle_key=None):
        with self._lock:
            return self._snapshot_locked(cycle_key)

    def _snapshot_locked(self, cycle_key):
        cycle_key = str(cycle_key or "").strip() or None
        same = bool(cycle_key) and cycle_key == self._cycle_key
        cycle = dict(self._cycle) if same else {s: 0 for s in SOURCES}
        return {
            "session_total": sum(self._session.values()),
            "session_by_source": dict(self._session),
            "cycle_key": cycle_key,
            "cycle_total": sum(cycle.values()),
            "cycle_by_source": cycle,
            "opened_at": self.opened_at,
            "last_at": self._last_at,
        }