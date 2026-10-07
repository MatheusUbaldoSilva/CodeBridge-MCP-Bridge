import tempfile
import unittest
from pathlib import Path

from rag.contracts import SourceType
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.vector_ids import (
    deterministic_chunk_id,
    deterministic_document_id,
    deterministic_vector_point_id,
    upsert_vector_chunk,
)
from rag.index.vector_namespace import build_project_namespace_filter
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION


class RagVectorDeterministicIdTests(unittest.TestCase):
    def test_document_id_is_deterministic(self):
        first = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            r"rag\index\vector_ids.py",
        )
        second = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            "rag/index/vector_ids.py",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("doc:"))
        self.assertEqual(len(first), 68)

    def test_document_id_changes_across_project_or_path(self):
        base = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            "src/main.py",
        )
        other_project = deterministic_document_id(
            "drones",
            SourceType.CODE,
            "src/main.py",
        )
        other_path = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            "src/other.py",
        )
        self.assertNotEqual(base, other_project)
        self.assertNotEqual(base, other_path)

    def test_chunk_id_is_deterministic_for_same_chunk(self):
        document_id = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            "src/main.py",
        )
        first = deterministic_chunk_id(
            document_id,
            3,
            "def run():\n    return 1",
        )
        second = deterministic_chunk_id(
            document_id,
            3,
            "def run():\n    return 1",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("chunk:"))
        self.assertEqual(len(first), 70)

    def test_chunk_id_changes_for_content_or_ordinal(self):
        document_id = deterministic_document_id(
            "codebridge",
            SourceType.CODE,
            "src/main.py",
        )
        base = deterministic_chunk_id(document_id, 0, "alpha")
        changed_content = deterministic_chunk_id(
            document_id,
            0,
            "beta",
        )
        changed_ordinal = deterministic_chunk_id(
            document_id,
            1,
            "alpha",
        )
        self.assertNotEqual(base, changed_content)
        self.assertNotEqual(base, changed_ordinal)

    def test_vector_point_id_is_stable_and_scoped(self):
        chunk_id = "chunk:" + ("a" * 64)
        text_a = deterministic_vector_point_id(
            "codebridge",
            TEXT_VECTOR_COLLECTION,
            chunk_id,
        )
        text_b = deterministic_vector_point_id(
            "codebridge",
            TEXT_VECTOR_COLLECTION,
            chunk_id,
        )
        code = deterministic_vector_point_id(
            "codebridge",
            CODE_VECTOR_COLLECTION,
            chunk_id,
        )
        other_project = deterministic_vector_point_id(
            "drones",
            TEXT_VECTOR_COLLECTION,
            chunk_id,
        )

        self.assertEqual(text_a, text_b)
        self.assertNotEqual(text_a, code)
        self.assertNotEqual(text_a, other_project)

    def test_reindex_same_text_chunk_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            client = open_qdrant_local(Path(td) / "qdrant")
            try:
                ensure_vector_collections(client)
                document_id = deterministic_document_id(
                    "codebridge",
                    SourceType.DOCUMENTATION,
                    "README.md",
                )
                chunk_id = deterministic_chunk_id(
                    document_id,
                    0,
                    "CodeBridge README chunk",
                )
                vector = [1.0] + [0.0] * (
                    TEXT_EMBEDDING_DIMENSION - 1
                )

                first_id = upsert_vector_chunk(
                    client,
                    collection_name=TEXT_VECTOR_COLLECTION,
                    project_id="codebridge",
                    chunk_id=chunk_id,
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "revision": 1,
                    },
                )
                second_id = upsert_vector_chunk(
                    client,
                    collection_name=TEXT_VECTOR_COLLECTION,
                    project_id="codebridge",
                    chunk_id=chunk_id,
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "revision": 2,
                    },
                )

                points, _ = client.scroll(
                    collection_name=TEXT_VECTOR_COLLECTION,
                    scroll_filter=build_project_namespace_filter(
                        "codebridge"
                    ),
                    limit=10,
                    with_payload=True,
                )

                self.assertEqual(first_id, second_id)
                self.assertEqual(len(points), 1)
                self.assertEqual(str(points[0].id), first_id)
                self.assertEqual(points[0].payload["chunk_id"], chunk_id)
                self.assertEqual(points[0].payload["revision"], 2)
            finally:
                close_qdrant_local(client)

    def test_reindex_same_code_chunk_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            client = open_qdrant_local(Path(td) / "qdrant")
            try:
                ensure_vector_collections(client)
                document_id = deterministic_document_id(
                    "new-world-pvp",
                    SourceType.CODE,
                    "src/game.cpp",
                )
                chunk_id = deterministic_chunk_id(
                    document_id,
                    7,
                    "void MoveItem() {}",
                )
                vector = [1.0] + [0.0] * (
                    CODE_EMBEDDING_DIMENSION - 1
                )

                for _ in range(3):
                    upsert_vector_chunk(
                        client,
                        collection_name=CODE_VECTOR_COLLECTION,
                        project_id="new-world-pvp",
                        chunk_id=chunk_id,
                        vector=vector,
                        payload={"document_id": document_id},
                    )

                points, _ = client.scroll(
                    collection_name=CODE_VECTOR_COLLECTION,
                    scroll_filter=build_project_namespace_filter(
                        "new-world-pvp"
                    ),
                    limit=10,
                    with_payload=True,
                )

                self.assertEqual(len(points), 1)
                self.assertEqual(points[0].payload["chunk_id"], chunk_id)
            finally:
                close_qdrant_local(client)

    def test_wrong_vector_dimension_is_rejected_before_upsert(self):
        with tempfile.TemporaryDirectory() as td:
            client = open_qdrant_local(Path(td) / "qdrant")
            try:
                ensure_vector_collections(client)
                with self.assertRaises(ValueError):
                    upsert_vector_chunk(
                        client,
                        collection_name=TEXT_VECTOR_COLLECTION,
                        project_id="codebridge",
                        chunk_id="chunk-x",
                        vector=[1.0, 0.0],
                    )
            finally:
                close_qdrant_local(client)


if __name__ == "__main__":
    unittest.main()
