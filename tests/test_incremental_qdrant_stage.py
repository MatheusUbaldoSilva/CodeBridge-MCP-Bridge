"""Qdrant isolated merge smoke with old-chunk removal and cross-project preservation."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_qdrant_stage import stage_incremental_qdrant, IncrementalQdrantError
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local


def seed(path, specs):
    from qdrant_client import models
    client = open_qdrant_local(path)
    try:
        for collection in ("text", "code"):
            client.create_collection(collection, vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
        for collection, pid, doc, chunk, number in specs:
            client.upsert(collection, points=[models.PointStruct(
                id=number, vector=[1.0, 0.0, 0.0],
                payload={"project_namespace":pid, "document_id":doc, "chunk_id":chunk},
            )], wait=True)
    finally:
        close_qdrant_local(client)


try:
    import qdrant_client  # noqa: F401
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False


@unittest.skipUnless(HAS_QDRANT, "qdrant-client indisponivel neste ambiente")
class QdrantStageTests(unittest.TestCase):
    def test_preserves_and_replaces(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old, new, output = (root / n for n in ("old", "new", "out"))
            seed(old, [("text", "a", "doc-a", "obsolete", 101),
                       ("text", "b", "doc-b", "kept", 102),
                       ("code", "a", "doc-x", "kept-code", 103)])
            seed(new, [("text", "a", "doc-a", "replacement", 201),
                       ("text", "a", "doc-c", "addition", 202)])
            result = stage_incremental_qdrant(old, new, output, "a")
            self.assertEqual(result["incoming_vectors"], 2)
            reader = open_qdrant_local(output)
            try:
                data, _ = reader.scroll("text", limit=100, with_payload=True)
                self.assertEqual({p.payload["chunk_id"] for p in data},
                                 {"kept", "replacement", "addition"})
                self.assertEqual(reader.count("code", exact=True).count, 1)
            finally:
                close_qdrant_local(reader)
            reader = open_qdrant_local(old)
            try:
                data, _ = reader.scroll("text", limit=100, with_payload=True)
                self.assertEqual({p.payload["chunk_id"] for p in data}, {"obsolete", "kept"})
            finally:
                close_qdrant_local(reader)

    def test_foreign_project_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old, new, output = (root / n for n in ("old", "new", "out"))
            seed(old, [])
            seed(new, [("text", "b", "other", "foreign", 501)])
            with self.assertRaises(IncrementalQdrantError):
                stage_incremental_qdrant(old, new, output, "a")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
