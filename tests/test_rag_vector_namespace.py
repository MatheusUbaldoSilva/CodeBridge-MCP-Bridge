import tempfile
import unittest
from pathlib import Path

from qdrant_client import models

from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.vector_namespace import (
    EXAMPLE_PROJECT_NAMESPACES,
    PROJECT_NAMESPACE_PAYLOAD_KEY,
    ProjectNamespace,
    build_project_namespace_filter,
    require_project_namespace,
    vector_payload_with_namespace,
)
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION


class RagVectorNamespaceTests(unittest.TestCase):
    def test_handoff_example_namespaces_are_valid(self):
        self.assertEqual(
            EXAMPLE_PROJECT_NAMESPACES,
            (
                "codebridge",
                "new-world-pvp",
                "drones",
                "outros",
            ),
        )
        for namespace in EXAMPLE_PROJECT_NAMESPACES:
            self.assertEqual(
                require_project_namespace(namespace),
                namespace,
            )

    def test_namespace_validation_is_strict_and_canonical(self):
        valid = (
            "a",
            "codebridge",
            "new-world-pvp",
            "project-123",
        )
        for item in valid:
            self.assertEqual(require_project_namespace(item), item)

        invalid = (
            "",
            " CodeBridge",
            "CodeBridge",
            "new world pvp",
            "new_world_pvp",
            "-codebridge",
            "codebridge-",
            "codebridge--rag",
            "ação",
            "a" * 65,
        )
        for item in invalid:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    require_project_namespace(item)

    def test_project_namespace_dataclass_exports_payload(self):
        namespace = ProjectNamespace("codebridge")
        self.assertEqual(
            namespace.as_payload(),
            {PROJECT_NAMESPACE_PAYLOAD_KEY: "codebridge"},
        )

    def test_payload_adds_namespace_without_losing_metadata(self):
        payload = vector_payload_with_namespace(
            "new-world-pvp",
            {
                "chunk_id": "chunk-1",
                "path": "src/game.cpp",
            },
        )
        self.assertEqual(
            payload[PROJECT_NAMESPACE_PAYLOAD_KEY],
            "new-world-pvp",
        )
        self.assertEqual(payload["chunk_id"], "chunk-1")
        self.assertEqual(payload["path"], "src/game.cpp")

    def test_conflicting_namespace_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            vector_payload_with_namespace(
                "codebridge",
                {PROJECT_NAMESPACE_PAYLOAD_KEY: "drones"},
            )

    def test_real_qdrant_filter_isolates_namespaces_in_text_collection(self):
        with tempfile.TemporaryDirectory() as td:
            client = open_qdrant_local(Path(td) / "qdrant")
            try:
                ensure_vector_collections(client)
                vector = [1.0] + [0.0] * (TEXT_EMBEDDING_DIMENSION - 1)

                client.upsert(
                    collection_name=TEXT_VECTOR_COLLECTION,
                    points=[
                        models.PointStruct(
                            id=1,
                            vector=vector,
                            payload=vector_payload_with_namespace(
                                "codebridge",
                                {"label": "cb"},
                            ),
                        ),
                        models.PointStruct(
                            id=2,
                            vector=vector,
                            payload=vector_payload_with_namespace(
                                "drones",
                                {"label": "dr"},
                            ),
                        ),
                    ],
                )

                points, _ = client.scroll(
                    collection_name=TEXT_VECTOR_COLLECTION,
                    scroll_filter=build_project_namespace_filter(
                        "codebridge"
                    ),
                    limit=10,
                    with_payload=True,
                )

                self.assertEqual(len(points), 1)
                self.assertEqual(points[0].id, 1)
                self.assertEqual(points[0].payload["label"], "cb")
                self.assertEqual(
                    points[0].payload[PROJECT_NAMESPACE_PAYLOAD_KEY],
                    "codebridge",
                )
            finally:
                close_qdrant_local(client)

    def test_real_qdrant_filter_isolates_namespaces_in_code_collection(self):
        with tempfile.TemporaryDirectory() as td:
            client = open_qdrant_local(Path(td) / "qdrant")
            try:
                ensure_vector_collections(client)
                vector = [1.0] + [0.0] * (CODE_EMBEDDING_DIMENSION - 1)

                client.upsert(
                    collection_name=CODE_VECTOR_COLLECTION,
                    points=[
                        models.PointStruct(
                            id=11,
                            vector=vector,
                            payload=vector_payload_with_namespace(
                                "new-world-pvp",
                                {"label": "nw"},
                            ),
                        ),
                        models.PointStruct(
                            id=12,
                            vector=vector,
                            payload=vector_payload_with_namespace(
                                "outros",
                                {"label": "other"},
                            ),
                        ),
                    ],
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
                self.assertEqual(points[0].id, 11)
                self.assertEqual(points[0].payload["label"], "nw")
            finally:
                close_qdrant_local(client)


if __name__ == "__main__":
    unittest.main()
