import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.index.sqlite_schema import connect_rag_index
from rag.index.manifest import IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.runtime.incremental_bundle_validate import (
    validate_incremental_bundle, IncrementalBundleValidationError,
)


def fixture(root):
    from qdrant_client import models
    db = connect_rag_index(root / "rag_index.sqlite3")
    digest = hashlib.sha256(b"hello").hexdigest()
    try:
        db.execute("INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256) "
                   "VALUES(?,?,?,?,?,?)", ("d1", "a", "DOCUMENTATION", "hello", "a.md", digest))
        db.execute("INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path) "
                   "VALUES(?,?,?,?,?,?,?)", ("c1", "d1", "a", 0, "hello", "DOCUMENTATION", "a.md"))
        db.commit()
    finally:
        db.close()
    save_index_manifest(root / "rag-index-manifest.json", IndexManifest((
        ManifestEntry(project_id="a", index_kind=ManifestIndexKind.TEXT, path="a.md",
                      size=5, mtime_ns=1, sha256=digest, chunk_ids=("c1",),
                      model_version="fixture"),
    )))
    q = open_qdrant_local(root / "qdrant")
    try:
        for collection in ("text", "code"):
            q.create_collection(collection, vectors_config=models.VectorParams(
                size=3, distance=models.Distance.COSINE))
        q.upsert("text", points=[models.PointStruct(
            id=42, vector=[1.0, 0.0, 0.0],
            payload={"project_namespace":"a", "chunk_id":"c1", "document_id":"d1"})])
    finally:
        close_qdrant_local(q)


class BundleValidationTests(unittest.TestCase):
    def test_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            result = validate_incremental_bundle(root)
            self.assertEqual((result["documents"], result["chunks"], result["vectors"]), (1,1,1))

    def test_missing_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            q = open_qdrant_local(root / "qdrant")
            try:
                q.set_payload("text", payload={"chunk_id": "wrong"}, points=[42])
            finally:
                close_qdrant_local(q)
            with self.assertRaises(IncrementalBundleValidationError):
                validate_incremental_bundle(root)


if __name__ == "__main__":
    unittest.main()
