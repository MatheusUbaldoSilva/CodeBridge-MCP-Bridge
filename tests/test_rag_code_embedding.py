import io
import json
import tempfile
import unittest
from pathlib import Path

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import (
    CODE_CORPUS_SOURCE_TYPES,
    CODE_EMBEDDING_BATCH_SIZE,
    CODE_EMBEDDING_DETERMINISM_MIN_COSINE,
    CODE_EMBEDDING_DIMENSION,
    CodeChunkEmbedding,
    CodeEmbeddingClient,
    CodeEmbeddingRole,
    CodeEmbeddingStateError,
    CodeEmbeddingValidationError,
    CodeEmbeddingVector,
    code_embeddings_are_deterministic,
)
from rag.models.code_lifecycle import CodeModelLifecycle, build_code_server_config
from rag.models.lifecycle import ModelLifecycleState


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()
        return False


class FakeProcess:
    pid = 7007
    def poll(self):
        return None


def unit_vector(index=0, value=1.0):
    result = [0.0] * CODE_EMBEDDING_DIMENSION
    result[index] = value
    return result


class RagCodeEmbeddingTests(unittest.TestCase):
    def ready_lifecycle(self, root):
        exe = root / "server.exe"; exe.write_bytes(b"x")
        model = root / "model.gguf"; model.write_bytes(b"x")
        lifecycle = CodeModelLifecycle(
            build_code_server_config(
                executable_path=exe,
                model_path=model,
                port=19140,
                log_path=root / "server.log",
            )
        )
        lifecycle._process = FakeProcess()
        lifecycle._resolved_port = 19140
        lifecycle._state = ModelLifecycleState.READY
        return lifecycle

    def opener(self, vectors, captured=None):
        queue = list(vectors)
        def call(request, timeout):
            if captured is not None:
                captured.append(json.loads(request.data.decode("utf-8")))
            payload = {"data":[{"index":0,"embedding":queue.pop(0)}]}
            return FakeResponse(json.dumps(payload).encode("utf-8"))
        return call

    def test_dimension_batch_and_corpus_are_frozen(self):
        self.assertEqual(CODE_EMBEDDING_DIMENSION, 1536)
        self.assertEqual(CODE_EMBEDDING_BATCH_SIZE, 1)
        self.assertEqual(CODE_EMBEDDING_DETERMINISM_MIN_COSINE, 0.9999)
        self.assertEqual(CODE_CORPUS_SOURCE_TYPES, (SourceType.CODE,))

    def test_nl2code_query_and_passage_use_distinct_prefixes(self):
        with tempfile.TemporaryDirectory() as td:
            captured = []
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener(
                    [unit_vector(1), unit_vector(2)],
                    captured,
                ),
            )
            client.embed_query(CodeRetrievalTask.NL2CODE, "ownership")
            client.embed_passage(CodeRetrievalTask.NL2CODE, "bool owns_item();")
        self.assertEqual(
            captured[0]["input"],
            "Find the most relevant code snippet given the following query:\nownership",
        )
        self.assertEqual(
            captured[1]["input"],
            "Candidate code snippet:\nbool owns_item();",
        )

    def test_code2code_query_prefix_is_task_specific(self):
        with tempfile.TemporaryDirectory() as td:
            captured = []
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([unit_vector()], captured),
            )
            client.embed_query(CodeRetrievalTask.CODE2CODE, "MoveItem(src, dst);")
        self.assertTrue(
            captured[0]["input"].startswith(
                "Find an equivalent code snippet given the following code snippet:\n"
            )
        )

    def test_non_code_chunk_is_rejected(self):
        chunk = Chunk(
            "c1", "d1", "handoff",
            SourceMetadata("p", SourceType.DOCUMENTATION, path="docs/x.md"),
        )
        with tempfile.TemporaryDirectory() as td:
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([]),
            )
            with self.assertRaises(CodeEmbeddingValidationError):
                client.embed_code_chunks([chunk])

    def test_code_chunk_preserves_exact_provenance(self):
        metadata = SourceMetadata(
            "project",
            SourceType.CODE,
            path="src/item.cpp",
            symbol="CHARACTER::MoveItem",
            line_start=120,
            line_end=150,
            git_branch="main",
            git_commit="a" * 40,
            sha256="b" * 64,
        )
        chunk = Chunk("chunk-item", "doc-item", "bool MoveItem() { return true; }", metadata)
        with tempfile.TemporaryDirectory() as td:
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([unit_vector(7)]),
            )
            result = client.embed_code_chunks([chunk])[0]
        self.assertIsInstance(result, CodeChunkEmbedding)
        self.assertEqual(result.chunk_id, chunk.chunk_id)
        self.assertEqual(result.document_id, chunk.document_id)
        self.assertEqual(result.metadata, metadata)
        self.assertEqual(result.embedding.dimension, 1536)
        self.assertEqual(result.embedding.role, CodeEmbeddingRole.PASSAGE)

    def test_non_code_passage_task_is_rejected_for_corpus(self):
        chunk = Chunk(
            "c1", "d1", "int x = 1;",
            SourceMetadata("p", SourceType.CODE, path="src/x.cpp"),
        )
        with tempfile.TemporaryDirectory() as td:
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([]),
            )
            with self.assertRaises(CodeEmbeddingValidationError):
                client.embed_code_chunks([chunk], task=CodeRetrievalTask.CODE2NL)

    def test_model_must_be_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            client = CodeEmbeddingClient(
                CodeModelLifecycle(
                    build_code_server_config(
                        executable_path=root / "server.exe",
                        model_path=root / "model.gguf",
                    )
                ),
                opener=lambda *a, **k: None,
            )
            with self.assertRaises(CodeEmbeddingStateError):
                client.embed_query(CodeRetrievalTask.NL2CODE, "x")

    def test_wrong_dimension_and_norm_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([[1.0, 0.0]]),
            )
            with self.assertRaises(CodeEmbeddingValidationError):
                client.embed_passage(CodeRetrievalTask.NL2CODE, "x")

        bad = unit_vector(value=2.0)
        with tempfile.TemporaryDirectory() as td:
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener([bad]),
            )
            with self.assertRaises(CodeEmbeddingValidationError):
                client.embed_passage(CodeRetrievalTask.NL2CODE, "x")

    def test_determinism_requires_same_task_and_role(self):
        first = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.PASSAGE,
            tuple(unit_vector(8)),
        )
        same = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.PASSAGE,
            tuple(unit_vector(8)),
        )
        other_task = CodeEmbeddingVector(
            CodeRetrievalTask.CODE2CODE,
            CodeEmbeddingRole.PASSAGE,
            tuple(unit_vector(8)),
        )
        self.assertTrue(code_embeddings_are_deterministic(first, same))
        self.assertFalse(code_embeddings_are_deterministic(first, other_task))

    def test_embed_passages_is_sequential(self):
        with tempfile.TemporaryDirectory() as td:
            captured = []
            client = CodeEmbeddingClient(
                self.ready_lifecycle(Path(td)),
                opener=self.opener(
                    [unit_vector(0), unit_vector(1), unit_vector(2)],
                    captured,
                ),
            )
            results = client.embed_passages(
                CodeRetrievalTask.NL2CODE,
                ("a", "b", "c"),
            )
        self.assertEqual(len(results), 3)
        self.assertEqual(len(captured), 3)


if __name__ == "__main__":
    unittest.main()
