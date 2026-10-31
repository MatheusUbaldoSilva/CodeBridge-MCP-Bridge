"""RAG-DEL-01.04-DQ-C: scratch-only private read session and lock order.

Factories must be supplied by tests/lab orchestrator. Do NOT plug these
fixtures into installed GUI/MCP or treat them as operational read guards.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, ContextManager, Any

from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab, _validated_scratch_catalog,
)


class PrivateReadSessionLabError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrivateLabPin:
    project_id: str
    sqlite: Path
    manifest: Path
    generation: str
    semantic_lock_held: bool
    operational_use_allowed: bool = False
    activation_authorized: bool = False
    _active: list[bool] = field(default_factory=lambda: [True], repr=False)

    def call_semantic_already_locked(self, callback: Callable[..., Any], *args, **kwargs):
        """Synthetic semantic executor contract: no internal lock acquisition."""
        if not self._active[0]:
            raise PrivateReadSessionLabError("private read session already closed")
        if not self.semantic_lock_held:
            raise PrivateReadSessionLabError("semantic lock not held by private read session")
        if not callable(callback):
            raise TypeError("semantic callback required")
        return callback(*args, **kwargs)


def _file_hash(path: Path) -> str:
    if (not path.is_file() or path.is_symlink()
            or (hasattr(path,"is_junction") and path.is_junction())):
        raise PrivateReadSessionLabError("private artifact unavailable or redirected")
    return sha256(path.read_bytes()).hexdigest()


@contextmanager
def private_read_session_lab(
    project_id: str, *, catalog_file: Path, sqlite_path: Path,
    manifest_path: Path, generation_guard_factory: Callable[[], ContextManager],
    semantic_guard_factory: Callable[[], ContextManager] | None = None,
    semantic: bool = False, timeout_seconds: float = 0.4,
    laboratory_mode: bool = False, operator_approved: bool = False,
):
    """Pin scratch catalog and both selected artifacts during a full read.

    Order: generation shared (supplied) -> semantic exclusive if requested
    (supplied) -> bounded catalog mutex. No queue lease is touched.
    """
    if laboratory_mode is not True or operator_approved is not True:
        raise PermissionError("private lab read requires explicit approval")
    if (not isinstance(project_id, str) or not project_id
            or project_id == "codebridge"
            or not callable(generation_guard_factory)
            or (semantic is not True and semantic is not False)
            or (semantic and not callable(semantic_guard_factory))):
        raise PrivateReadSessionLabError("invalid private lab read guard contract")
    catalog, root = _validated_scratch_catalog(catalog_file)
    db = Path(sqlite_path).absolute()
    manifest = Path(manifest_path).absolute()
    for p, filename in ((db,"rag_index.sqlite3"),(manifest,"rag-index-manifest.json")):
        if (p.name != filename or not p.is_file() or p.is_symlink()
                or not p.resolve(strict=True).is_relative_to(root)
                or p.parent.parent != root / "generations"):
            raise PrivateReadSessionLabError("private artifacts outside scratch generation")
    if db.parent != manifest.parent:
        raise PrivateReadSessionLabError("private SQLite and manifest must share generation")
    with ExitStack() as stack:
        stack.enter_context(generation_guard_factory())
        if semantic:
            stack.enter_context(semantic_guard_factory())
        stack.enter_context(bounded_catalog_mutex_lab(
            catalog, timeout_seconds=timeout_seconds,
            laboratory_mode=True, operator_approved=True,
        ))
        raw = catalog.read_bytes()
        obj = json.loads(raw.decode("utf-8-sig"))
        if obj.get("schema_version") != 1 or not isinstance(obj.get("projects"),dict):
            raise PrivateReadSessionLabError("invalid scratch catalog schema")
        row = obj["projects"].get(project_id)
        if (not isinstance(row,dict) or row.get("enabled") is not True
                or row.get("project_id") != project_id
                or row.get("generation_directory") != str(db.parent.resolve())):
            raise PrivateReadSessionLabError("scratch private catalog registration mismatch")
        sqlite_hash = _file_hash(db)
        manifest_hash = _file_hash(manifest)
        if row.get("sqlite_sha256") != sqlite_hash or row.get("manifest_sha256") != manifest_hash:
            raise PrivateReadSessionLabError("scratch private index fingerprint drift")
        pinned = PrivateLabPin(
            project_id=project_id, sqlite=db, manifest=manifest,
            generation=db.parent.name, semantic_lock_held=semantic,
        )
        try:
            yield pinned
            # Validate while all locks are still held.
            if (catalog.read_bytes() != raw or _file_hash(db) != sqlite_hash
                    or _file_hash(manifest) != manifest_hash):
                raise PrivateReadSessionLabError("private session changed while pinned")
        finally:
            pinned._active[0] = False
