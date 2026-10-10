"""Read-only cross-store verification of a closed, isolated RAG bundle."""
from pathlib import Path
import sqlite3

from rag.index.manifest import load_index_manifest
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local


class IncrementalBundleValidationError(RuntimeError):
    pass


def validate_incremental_bundle(folder):
    root = Path(folder).resolve()
    db_path = root / "rag_index.sqlite3"
    manifest_path = root / "rag-index-manifest.json"
    vectors_path = root / "qdrant"
    if not db_path.is_file() or not manifest_path.is_file() or not vectors_path.is_dir():
        raise IncrementalBundleValidationError("incomplete bundle")
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise IncrementalBundleValidationError("SQLite integrity failed")
        docs = conn.execute(
            "SELECT document_id,project_id,path,source_type,sha256 FROM rag_documents"
        ).fetchall()
        chunks = conn.execute(
            "SELECT chunk_id,document_id,project_id,source_type FROM rag_chunks"
        ).fetchall()
        invalid = conn.execute(
            "SELECT count(*) FROM rag_chunks c LEFT JOIN rag_documents d "
            "ON c.document_id=d.document_id WHERE d.document_id IS NULL "
            "OR c.project_id!=d.project_id"
        ).fetchone()[0]
        if invalid:
            raise IncrementalBundleValidationError("orphan or cross-project chunks")
        expected = {
            ("code" if source == "CODE" else "text", project, chunk)
            for chunk, doc, project, source in chunks
        }
        if len(expected) != len(chunks):
            raise IncrementalBundleValidationError("duplicate chunk identity")
        doc_chunks = {}
        for chunk, doc, project, source in chunks:
            doc_chunks.setdefault(doc, set()).add(chunk)
    finally:
        conn.close()
    manifest = load_index_manifest(manifest_path)
    # Every indexed document must have a matching manifest path/hash and chunks.
    covered = set()
    for doc, project, path, source, digest in docs:
        matching = [entry for entry in manifest.entries if
                    entry.project_id == project and entry.path == path and
                    entry.sha256 == digest and set(entry.chunk_ids) == doc_chunks.get(doc, set())]
        if len(matching) != 1:
            raise IncrementalBundleValidationError("manifest mismatch: " + str(path))
        covered.add(matching[0].key)
    if len(covered) != len(manifest.entries):
        raise IncrementalBundleValidationError("unmatched manifest entries")
    client = open_qdrant_local(vectors_path)
    try:
        actual = set()
        for collection in ("text", "code"):
            offset = None
            while True:
                page, offset = client.scroll(
                    collection_name=collection, limit=128, offset=offset,
                    with_payload=True, with_vectors=False)
                for point in page:
                    payload = point.payload or {}
                    key = (collection, payload.get("project_namespace"), payload.get("chunk_id"))
                    if key in actual:
                        raise IncrementalBundleValidationError("duplicate vector identity")
                    actual.add(key)
                if offset is None:
                    break
    finally:
        close_qdrant_local(client)
    if actual != expected:
        raise IncrementalBundleValidationError(
            f"vector mismatch: missing={len(expected - actual)}, extra={len(actual - expected)}")
    return {"state": "VALIDATED_OFFLINE_NOT_PUBLISHED",
            "documents": len(docs), "chunks": len(chunks),
            "vectors": len(actual), "manifest_entries": len(manifest.entries)}
