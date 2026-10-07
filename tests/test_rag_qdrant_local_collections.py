import importlib.metadata
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qdrant_client import models

from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    QDRANT_DISTANCE,
    TEXT_VECTOR_COLLECTION,
    VECTOR_COLLECTION_SPECS,
    QdrantCollectionContractError,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
    resolve_qdrant_local_path,
)
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION


ROOT = Path(__file__).resolve().parents[1]


class RagQdrantLocalCollectionsTests(unittest.TestCase):
    def test_dependency_version_matches_frozen_policy(self):
        self.assertEqual(
            importlib.metadata.version("qdrant-client"),
            "1.19.1",
        )

    def test_adapter_module_import_is_qdrant_lazy(self):
        script = (
            "import sys; "
            "import rag.index.qdrant_local; "
            "print('LOADED=' + str('qdrant_client' in sys.modules))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("LOADED=False", completed.stdout)

    def test_collection_contract_is_text_and_code(self):
        specs = {spec.name: spec for spec in VECTOR_COLLECTION_SPECS}

        self.assertEqual(
            set(specs),
            {TEXT_VECTOR_COLLECTION, CODE_VECTOR_COLLECTION},
        )
        self.assertEqual(
            specs[TEXT_VECTOR_COLLECTION].dimension,
            TEXT_EMBEDDING_DIMENSION,
        )
        self.assertEqual(
            specs[CODE_VECTOR_COLLECTION].dimension,
            CODE_EMBEDDING_DIMENSION,
        )
        self.assertTrue(
            all(spec.distance == QDRANT_DISTANCE for spec in specs.values())
        )

    def test_real_local_storage_creates_separate_collections(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "qdrant"
            client = open_qdrant_local(path)
            try:
                result = ensure_vector_collections(client)
                names = {
                    item.name
                    for item in client.get_collections().collections
                }
                text_vectors = (
                    client.get_collection(TEXT_VECTOR_COLLECTION)
                    .config.params.vectors
                )
                code_vectors = (
                    client.get_collection(CODE_VECTOR_COLLECTION)
                    .config.params.vectors
                )

                self.assertEqual(result, VECTOR_COLLECTION_SPECS)
                self.assertEqual(
                    names,
                    {TEXT_VECTOR_COLLECTION, CODE_VECTOR_COLLECTION},
                )
                self.assertEqual(
                    text_vectors.size,
                    TEXT_EMBEDDING_DIMENSION,
                )
                self.assertEqual(
                    code_vectors.size,
                    CODE_EMBEDDING_DIMENSION,
                )
                self.assertEqual(
                    str(text_vectors.distance),
                    QDRANT_DISTANCE,
                )
                self.assertEqual(
                    str(code_vectors.distance),
                    QDRANT_DISTANCE,
                )
            finally:
                close_qdrant_local(client)

            self.assertTrue(path.exists())

    def test_reopen_is_persistent_and_ensure_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "qdrant"

            first = open_qdrant_local(path)
            try:
                ensure_vector_collections(first)
            finally:
                close_qdrant_local(first)

            second = open_qdrant_local(path)
            try:
                ensure_vector_collections(second)
                ensure_vector_collections(second)
                names = [
                    item.name
                    for item in second.get_collections().collections
                ]
                self.assertEqual(
                    sorted(names),
                    [CODE_VECTOR_COLLECTION, TEXT_VECTOR_COLLECTION],
                )
            finally:
                close_qdrant_local(second)

    def test_wrong_existing_dimension_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "qdrant"
            client = open_qdrant_local(path)
            try:
                client.create_collection(
                    collection_name=TEXT_VECTOR_COLLECTION,
                    vectors_config=models.VectorParams(
                        size=3,
                        distance=models.Distance.COSINE,
                    ),
                )

                with self.assertRaises(QdrantCollectionContractError):
                    ensure_vector_collections(client)
            finally:
                client.close()

    def test_explicit_path_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            selected = Path(td) / "vectors"
            self.assertEqual(
                resolve_qdrant_local_path(selected),
                selected,
            )


if __name__ == "__main__":
    unittest.main()
