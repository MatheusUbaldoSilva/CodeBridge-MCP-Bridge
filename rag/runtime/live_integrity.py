"""Live CodeBridge RAG cross-store audit without touching Qdrant clients.

This checks observed identities only. It is NOT a frozen snapshot, a backup,
or an authorization to modify production storage.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import pickletools
import sqlite3
import uuid

from rag.index.manifest import load_index_manifest
from rag.index.vector_ids import deterministic_vector_point_id
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.runtime.status import resolve_rag_state_directory


class LiveIntegrityError(RuntimeError):
    pass


def _decode_safe_point_uuid(encoded: str) -> str:
    """Inspect Qdrant Local's pickle-format key without unpickling it."""
    try:
        operations = list(pickletools.genops(base64.b64decode(encoded, validate=True)))
        permitted = {"PROTO", "FRAME", "SHORT_BINUNICODE", "BINUNICODE", "MEMOIZE", "STOP"}
        if not operations or operations[-1][0].name != "STOP":
            raise ValueError("point ID terminator missing")
        if any(op.name not in permitted for op, _, _ in operations):
            raise ValueError("unsafe point ID opcode")
        values = [arg for op, arg, _ in operations
                  if op.name in {"SHORT_BINUNICODE", "BINUNICODE"}]
        if len(values) != 1 or str(uuid.UUID(values[0])) != values[0]:
            raise ValueError("point ID is not a canonical UUID")
        return values[0]
    except (ValueError, TypeError, UnicodeError, OverflowError) as exc:
        raise LiveIntegrityError("malformed Qdrant Local point key") from exc


def _read_only_db(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise LiveIntegrityError("required SQLite file unavailable")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def inspect_live_index(project_id: str = "codebridge") -> dict:
    if project_id != "codebridge":
        raise PermissionError("live RAG integrity limited to approved project codebridge")
    root = resolve_rag_state_directory().resolve()
    db_path = root / "rag_index.sqlite3"
    manifest_path = root / "rag-index-manifest.json"
    qdrant = root / "qdrant"
    meta_path = qdrant / "meta.json"
    vector_dbs = {
        name: qdrant / "collection" / name / "storage.sqlite"
        for name in ("text", "code")
    }
    files = [db_path, manifest_path, meta_path, *vector_dbs.values()]
    if any(not p.is_file() for p in files):
        raise LiveIntegrityError("active RAG storage incomplete")
    before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}

    db = _read_only_db(db_path)
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise LiveIntegrityError("main SQLite integrity failed")
        docs = db.execute(
            "SELECT document_id, project_id, path, sha256 FROM rag_documents"
        ).fetchall()
        chunks = db.execute(
            "SELECT chunk_id, document_id, project_id, source_type FROM rag_chunks"
        ).fetchall()
        orphaned = db.execute(
            "SELECT count(*) FROM rag_chunks c LEFT JOIN rag_documents d "
            "ON c.document_id=d.document_id WHERE d.document_id IS NULL "
            "OR c.project_id!=d.project_id"
        ).fetchone()[0]
    finally:
        db.close()
    if orphaned:
        raise LiveIntegrityError("orphaned or cross-project chunks")
    if any(doc[1] != project_id for doc in docs):
        raise LiveIntegrityError("unexpected project in active SQLite index")

    grouped = {}
    for chunk_id, document_id, project, kind in chunks:
        grouped.setdefault(document_id, set()).add(chunk_id)
    manifest = load_index_manifest(manifest_path)
    indexed = {(item.project_id, item.path, item.sha256,
                frozenset(item.chunk_ids)) for item in manifest.entries}
    actual_docs = {(project, path, digest, frozenset(grouped.get(doc_id, ())))
                   for doc_id, project, path, digest in docs}
    if len(manifest.entries) != len(indexed) or actual_docs != indexed:
        raise LiveIntegrityError("manifest does not match document and chunk hashes")

    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    dims = {"text": TEXT_EMBEDDING_DIMENSION, "code": CODE_EMBEDDING_DIMENSION}
    expected = {"text": set(), "code": set()}
    for chunk_id, document_id, project, source_type in chunks:
        collection = "code" if source_type == "CODE" else "text"
        point_id = deterministic_vector_point_id(project, collection, chunk_id)
        if point_id in expected[collection]:
            raise LiveIntegrityError("duplicate deterministic vector ID")
        expected[collection].add(point_id)

    collections = {}
    for name, path in vector_dbs.items():
        definition = meta.get("collections", {}).get(name, {}).get("vectors", {})
        if definition.get("size") != dims[name] or definition.get("distance") != "Cosine":
            raise LiveIntegrityError("incompatible vector dimension or metric: " + name)
        conn = _read_only_db(path)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LiveIntegrityError("vector SQLite integrity failed: " + name)
            actual = [_decode_safe_point_uuid(row[0])
                      for row in conn.execute("SELECT id FROM points")]
        finally:
            conn.close()
        if len(actual) != len(set(actual)) or set(actual) != expected[name]:
            raise LiveIntegrityError("vector identity mismatch: " + name)
        collections[name] = {"vectors": len(actual), "dimension": dims[name],
                             "missing": 0, "extra": 0, "integrity": "ok"}

    after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}
    if before != after:
        raise LiveIntegrityError("RAG storage changed during live read; retry offline")
    return {
        "state": "OBSERVED_CONSISTENT",
        "project_id": project_id,
        "read_only": True,
        "snapshot_consistent": False,
        "safe_to_publish": False,
        "documents": len(docs),
        "chunks": len(chunks),
        "manifest_entries": len(manifest.entries),
        "collections": collections,
        "note": "Live observation only; external quiescence and atomic generation validation still required",
    }