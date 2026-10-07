import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.models.embedding import (
    TEXT_DOCUMENT_SOURCE_TYPES,
    TEXT_EMBEDDING_BATCH_SIZE,
    TEXT_EMBEDDING_DETERMINISM_MIN_COSINE,
    TEXT_EMBEDDING_DIMENSION,
    TEXT_EMBEDDING_NORM_TOLERANCE,
    DocumentChunkEmbedding,
    TextEmbeddingClient,
    TextEmbeddingProtocolError,
    TextEmbeddingRole,
    TextEmbeddingStateError,
    TextEmbeddingValidationError,
    TextEmbeddingVector,
    cosine_similarity,
    embeddings_are_deterministic,
)
from rag.models.lifecycle import (
    LlamaServerConfig,
    ModelLifecycleState,
    TextModelLifecycle,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class FakeProcess:
    pid = 1234

    def poll(self):
        return None


def unit_vector(
    *,
    index=0,
    value=1.0,
):
    values = [0.0] * TEXT_EMBEDDING_DIMENSION
    values[index] = value
    return values


class RagTextEmbeddingTests(unittest.TestCase):
    def ready_lifecycle(self, root: Path):
        executable = root / "llama-server.exe"
        model = root / "model.gguf"
        executable.write_bytes(b"x")
        model.write_bytes(b"x")

        lifecycle = TextModelLifecycle(
            LlamaServerConfig(
                executable_path=executable,
                model_path=model,
                port=19081,
                log_path=root / "server.log",
            )
        )
        lifecycle._process = FakeProcess()
        lifecycle._resolved_port = 19081
        lifecycle._state = ModelLifecycleState.READY
        return lifecycle

    def opener_for_vectors(
        self,
        vectors,
        captured_payloads=None,
    ):
        queue = list(vectors)

        def opener(request, timeout):
            if captured_payloads is not None:
                captured_payloads.append(
                    json.loads(
                        request.data.decode("utf-8")
                    )
                )

            vector = queue.pop(0)
            payload = {
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": vector,
                    }
                ],
                "model": "fixture.gguf",
                "usage": {},
            }
            return FakeResponse(
                json.dumps(payload).encode("utf-8")
            )

        return opener

    def test_dimension_and_batch_policy_are_frozen(self):
        self.assertEqual(
            TEXT_EMBEDDING_DIMENSION,
            1024,
        )
        self.assertEqual(
            TEXT_EMBEDDING_BATCH_SIZE,
            1,
        )
        self.assertEqual(
            TEXT_EMBEDDING_DETERMINISM_MIN_COSINE,
            0.9999,
        )

    def test_text_corpus_excludes_code(self):
        self.assertEqual(
            TEXT_DOCUMENT_SOURCE_TYPES,
            (
                SourceType.DOCUMENTATION,
                SourceType.AUDIT,
                SourceType.LOG,
                SourceType.GIT,
                SourceType.EXECUTION,
            ),
        )
        self.assertNotIn(
            SourceType.CODE,
            TEXT_DOCUMENT_SOURCE_TYPES,
        )

    def test_query_uses_query_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            captured = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener_for_vectors(
                    [unit_vector()],
                    captured,
                ),
            )

            vector = client.embed_query(
                "onde está o handoff?"
            )

        self.assertEqual(
            vector.role,
            TextEmbeddingRole.QUERY,
        )
        self.assertEqual(
            captured,
            [
                {
                    "input": (
                        "Query: "
                        "onde está o handoff?"
                    )
                }
            ],
        )

    def test_document_uses_document_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            captured = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener_for_vectors(
                    [unit_vector(index=2)],
                    captured,
                ),
            )

            vector = client.embed_document(
                "handoff do projeto"
            )

        self.assertEqual(
            vector.role,
            TextEmbeddingRole.DOCUMENT,
        )
        self.assertEqual(
            captured,
            [
                {
                    "input": (
                        "Document: "
                        "handoff do projeto"
                    )
                }
            ],
        )

    def test_model_must_be_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = LlamaServerConfig(
                executable_path=root / "server.exe",
                model_path=root / "model.gguf",
                port=19081,
            )
            lifecycle = TextModelLifecycle(config)
            client = TextEmbeddingClient(
                lifecycle,
                opener=lambda *a, **k: None,
            )

            with self.assertRaises(
                TextEmbeddingStateError
            ):
                client.embed_query("test")

    def test_response_requires_exact_dimension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TextEmbeddingClient(
                self.ready_lifecycle(
                    Path(temp_dir)
                ),
                opener=self.opener_for_vectors(
                    [[1.0, 0.0]]
                ),
            )

            with self.assertRaises(
                TextEmbeddingValidationError
            ):
                client.embed_document("test")

    def test_response_requires_unit_normalization(self):
        bad = unit_vector(value=2.0)
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TextEmbeddingClient(
                self.ready_lifecycle(
                    Path(temp_dir)
                ),
                opener=self.opener_for_vectors(
                    [bad]
                ),
            )

            with self.assertRaises(
                TextEmbeddingValidationError
            ):
                client.embed_document("test")

    def test_norm_tolerance_accepts_small_float_noise(self):
        values = unit_vector()
        values[0] = 1.0 + (
            TEXT_EMBEDDING_NORM_TOLERANCE
            / 2
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            client = TextEmbeddingClient(
                self.ready_lifecycle(
                    Path(temp_dir)
                ),
                opener=self.opener_for_vectors(
                    [values]
                ),
            )

            vector = client.embed_document(
                "test"
            )

        self.assertEqual(
            vector.dimension,
            1024,
        )

    def test_protocol_requires_single_data_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lifecycle = self.ready_lifecycle(
                Path(temp_dir)
            )

            def opener(request, timeout):
                return FakeResponse(
                    json.dumps(
                        {
                            "data": [],
                        }
                    ).encode("utf-8")
                )

            client = TextEmbeddingClient(
                lifecycle,
                opener=opener,
            )

            with self.assertRaises(
                TextEmbeddingProtocolError
            ):
                client.embed_document("test")

    def test_embed_documents_is_sequential_one_request_per_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            captured = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener_for_vectors(
                    [
                        unit_vector(index=0),
                        unit_vector(index=1),
                        unit_vector(index=2),
                    ],
                    captured,
                ),
            )

            vectors = client.embed_documents(
                ("a", "b", "c")
            )

        self.assertEqual(len(vectors), 3)
        self.assertEqual(len(captured), 3)
        self.assertEqual(
            [item["input"] for item in captured],
            [
                "Document: a",
                "Document: b",
                "Document: c",
            ],
        )

    def test_document_chunks_preserve_identity_and_metadata(self):
        metadata = SourceMetadata(
            project_id="project",
            source_type=SourceType.DOCUMENTATION,
            path="docs/readme.md",
            sha256="a" * 64,
        )
        chunk = Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="document content",
            metadata=metadata,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            client = TextEmbeddingClient(
                self.ready_lifecycle(
                    Path(temp_dir)
                ),
                opener=self.opener_for_vectors(
                    [unit_vector(index=4)]
                ),
            )

            result = client.embed_document_chunks(
                [chunk]
            )[0]

        self.assertIsInstance(
            result,
            DocumentChunkEmbedding,
        )
        self.assertEqual(
            result.chunk_id,
            "chunk-1",
        )
        self.assertEqual(
            result.document_id,
            "doc-1",
        )
        self.assertEqual(
            result.metadata,
            metadata,
        )
        self.assertEqual(
            result.embedding.role,
            TextEmbeddingRole.DOCUMENT,
        )

    def test_code_chunk_is_rejected_from_text_corpus(self):
        metadata = SourceMetadata(
            project_id="project",
            source_type=SourceType.CODE,
            path="src/main.py",
        )
        chunk = Chunk(
            chunk_id="code-1",
            document_id="code-doc",
            content="def run(): pass",
            metadata=metadata,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            client = TextEmbeddingClient(
                self.ready_lifecycle(
                    Path(temp_dir)
                ),
                opener=self.opener_for_vectors(
                    [],
                ),
            )

            with self.assertRaises(
                TextEmbeddingValidationError
            ):
                client.embed_document_chunks(
                    [chunk]
                )

    def test_cosine_similarity_and_determinism_contract(self):
        first = TextEmbeddingVector(
            role=TextEmbeddingRole.QUERY,
            values=tuple(unit_vector(index=8)),
        )
        same = TextEmbeddingVector(
            role=TextEmbeddingRole.QUERY,
            values=tuple(unit_vector(index=8)),
        )
        different_role = TextEmbeddingVector(
            role=TextEmbeddingRole.DOCUMENT,
            values=tuple(unit_vector(index=8)),
        )

        self.assertEqual(
            cosine_similarity(
                first.values,
                same.values,
            ),
            1.0,
        )
        self.assertTrue(
            embeddings_are_deterministic(
                first,
                same,
            )
        )
        self.assertFalse(
            embeddings_are_deterministic(
                first,
                different_role,
            )
        )

    def test_non_finite_vector_is_rejected(self):
        values = unit_vector()
        values[0] = float("nan")

        with self.assertRaises(ValueError):
            TextEmbeddingVector(
                role=TextEmbeddingRole.QUERY,
                values=tuple(values),
            )

    def test_no_cache_or_vector_store_is_implemented_here(self):
        import rag.models.embedding as module

        source = Path(
            module.__file__
        ).read_text(
            encoding="utf-8"
        ).lower()

        self.assertNotIn("sqlite", source)
        self.assertNotIn("qdrant", source)
        self.assertNotIn("cache", source.replace(
            "cache vectors",
            ""
        ))


if __name__ == "__main__":
    unittest.main()
