"""End-to-end offline incremental bundle merge using real SQLite and Qdrant."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.index.sqlite_schema import connect_rag_index
from rag.index.manifest import IndexManifest, ManifestEntry, ManifestIndexKind, save_index_manifest
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.index.vector_ids import deterministic_vector_point_id
from rag.runtime.incremental_bundle_stage import stage_incremental_bundle
from rag.runtime.incremental_bundle_validate import validate_incremental_bundle


def create_bundle(root, documents):
    from qdrant_client import models
    root.mkdir()
    database = connect_rag_index(root / "rag_index.sqlite3")
    entries = []
    try:
        for idx, (project, name, content) in enumerate(documents):
            document_id = project + "-" + name
            chunk = "chunk-" + document_id + "-" + content
            digest = hashlib.sha256(content.encode()).hexdigest()
            path = name + ".md"
            database.execute(
                "INSERT INTO rag_documents(document_id,project_id,source_type,content,path,sha256)"
                " VALUES(?,?,?,?,?,?)",
                (document_id, project, "DOCUMENTATION", content, path, digest))
            database.execute(
                "INSERT INTO rag_chunks(chunk_id,document_id,project_id,ordinal,content,source_type,path)"
                " VALUES(?,?,?,?,?,?,?)",
                (chunk, document_id, project, 0, content, "DOCUMENTATION", path))
            entries.append(ManifestEntry(
                project_id=project, index_kind=ManifestIndexKind.TEXT, path=path,
                size=len(content), mtime_ns=1, sha256=digest,
                chunk_ids=(chunk,), model_version="fixture"))
        database.commit()
    finally:
        database.close()
    save_index_manifest(root / "rag-index-manifest.json", IndexManifest(tuple(entries)))
    q = open_qdrant_local(root / "qdrant")
    try:
        for collection in ("text", "code"):
            q.create_collection(collection, vectors_config=models.VectorParams(
                size=3, distance=models.Distance.COSINE))
        points = []
        for idx, (project, name, content) in enumerate(documents):
            document_id = project + "-" + name
            points.append(models.PointStruct(
                id=deterministic_vector_point_id(project, "text", "chunk-" + document_id + "-" + content),
                vector=[1.0, 0.0, 0.0], payload={
                    "project_namespace": project, "document_id": document_id,
                    "chunk_id": "chunk-" + document_id + "-" + content}))
        q.upsert("text", points=points, wait=True)
    finally:
        close_qdrant_local(q)


class EndToEndBundleTests(unittest.TestCase):
    def test_add_update_preserve_and_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new, output = root/"old", root/"new", root/"merged"
            create_bundle(old, [("a", "first", "original"), ("b", "other", "preserved")])
            create_bundle(new, [("a", "first", "revised"), ("a", "second", "new")])
            old_hash = hashlib.sha256((old/"rag_index.sqlite3").read_bytes()).hexdigest()
            result = stage_incremental_bundle(old, new, output, "a")
            self.assertEqual(result["state"], "BUNDLE_VALIDATED_NOT_PUBLISHED")
            self.assertFalse(result["validated_for_publish"])
            self.assertEqual(result["verification"]["documents"], 3)
            self.assertEqual(result["verification"]["chunks"], 3)
            self.assertEqual(result["verification"]["vectors"], 3)
            self.assertEqual(hashlib.sha256((old/"rag_index.sqlite3").read_bytes()).hexdigest(), old_hash)
            self.assertEqual(validate_incremental_bundle(output)["manifest_entries"], 3)


if __name__ == "__main__":
    unittest.main()
