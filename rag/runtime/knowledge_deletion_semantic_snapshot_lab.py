"""DQ-E-D-3C-B: read-only TEMP private SQLite snapshot on the real worker.

This probes the exact pinned generation and private namespace, not semantics.
No Qdrant, model, real catalog, installed process or deletion operations.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3

from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    _validated_scratch_catalog,
)
from rag.runtime.knowledge_deletion_semantic_request_lab import (
    PinnedSemanticRequestV1, verify_pinned_semantic_request_lab,
)
from rag.runtime.knowledge_deletion_pin_ipc_lab import PinEnvelopeLabError


class PinnedSemanticSnapshotLabError(RuntimeError):
    pass


def read_pinned_semantic_snapshot_lab(
    request: PinnedSemanticRequestV1, *, catalog_file: Path,
    laboratory_mode: bool = False,
) -> dict:
    if laboratory_mode is not True:
        raise PermissionError("scratch private SQLite read must be explicitly enabled")
    if type(request) is not PinnedSemanticRequestV1:
        raise PinnedSemanticSnapshotLabError("strict typed pinned request required")
    # Checks catalog/project/generation/manifest/SQLite before opening the DB.
    evidence = verify_pinned_semantic_request_lab(
        request,catalog_file=catalog_file,laboratory_mode=True,
    )
    catalog, root = _validated_scratch_catalog(catalog_file)
    db = root/"generations"/request.pin.generation_id/"rag_index.sqlite3"
    if (not db.is_file() or db.is_symlink()
            or (hasattr(db,"is_junction") and db.is_junction())
            or not db.resolve(strict=True).is_relative_to(root)):
        raise PinnedSemanticSnapshotLabError("redirected or missing pinned SQLite")
    try:
        uri=db.resolve(strict=True).as_uri()+"?mode=ro"
        with closing(sqlite3.connect(uri,uri=True,timeout=0.2)) as cn:
            cn.execute("PRAGMA query_only=ON")
            # No SELECT * or document content. Count only approved namespace.
            count=cn.execute(
                "SELECT COUNT(*) FROM rag_documents WHERE project_id=?",
                (request.pin.project_id,),
            ).fetchone()[0]
    except sqlite3.Error as exc:
        raise PinnedSemanticSnapshotLabError("approved private namespace unreadable") from exc
    if type(count) is not int or count<0:
        raise PinnedSemanticSnapshotLabError("unexpected private namespace count")
    # Fail closed if anything changed during the snapshot. Assumes parent
    # maintains generation/semantic/catalog locks; worker does not attest it.
    verify_pinned_semantic_request_lab(
        request,catalog_file=catalog,laboratory_mode=True,
    )
    return {
        "state":"LAB_PINNED_SQLITE_NAMESPACE_READ_ONLY",
        "project_id":evidence["project_id"],
        "generation_id":evidence["generation_id"],
        "nonce":evidence["nonce"],
        "request_sha256":evidence["request_sha256"],
        "matching_private_document_count":count,
        "model_executed":False,
        "qdrant_accessed":False,
        "parent_locks_attested_by_worker":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
    }