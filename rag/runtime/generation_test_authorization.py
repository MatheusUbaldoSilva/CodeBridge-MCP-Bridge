"""Ephemeral, one-shot authorization for isolated generation publication tests.

Not connected to the Qt simulation or any production RAG directory.
"""
from __future__ import annotations
from pathlib import Path
from threading import Lock
from rag.runtime.incremental_preview_confirmation import revalidate_preview
from rag.runtime.generation_backup_publish import publish_with_verified_backup


class TestPublicationAuthorization:
    def __init__(self, root, previous, candidate, project, folder, snapshot):
        base = Path(root).resolve()
        if "codebridge-rag-generation-test" not in {p.lower() for p in base.parts}:
            raise ValueError("isolated test root required")
        if not previous or not candidate or previous == candidate:
            raise ValueError("invalid generation transition")
        self._root = base
        self._previous = previous
        self._candidate = candidate
        self._project = project
        self._folder = str(Path(folder).resolve())
        self._snapshot = snapshot
        self._lock = Lock()
        self._used = False

    def execute(self, *, confirmed, backup_name):
        # Consume even if confirmation is refused or a later validation fails.
        with self._lock:
            if self._used:
                raise ValueError("authorization attempt already consumed")
            self._used = True
        if confirmed is not True:
            raise ValueError("explicit confirmation required")
        revalidate_preview(self._snapshot, self._project, self._folder)
        return publish_with_verified_backup(
            self._root, self._previous, self._candidate, backup_name)
