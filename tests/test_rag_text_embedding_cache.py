import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.index.embedding_cache import (
    DEFAULT_TEXT_EMBEDDING_CACHE_FILENAME,
    TEXT_EMBEDDING_CACHE_SCHEMA_VERSION,
    TEXT_EMBEDDING_CACHE_TABLE,
    TextEmbeddingCache,
    TextEmbeddingCacheIntegrityError,
    TextEmbeddingCacheVersionError,
    connect_text_embedding_cache,
    initialize_text_embedding_cache,
    resolve_text_embedding_cache_path,
)
from rag.models.embedding import (
    TEXT_EMBEDDING_CACHE_NAMESPACE,
    TEXT_EMBEDDING_DIMENSION,
    CachedDocumentChunkEmbedding,
    TextEmbeddingClient,
    chunk_content_sha256,
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
    pid = 2222

    def poll(self):
        return None


def unit_vector(index=0):
    values = [0.0] * TEXT_EMBEDDING_DIMENSION
    values[index] = 1.0
    return values


class RagTextEmbeddingCacheTests(unittest.TestCase):
    def ready_lifecycle(self, root: Path):
        executable = root / "server.exe"
        model = root / "model.gguf"
        executable.write_bytes(b"x")
        model.write_bytes(b"x")
        lifecycle = TextModelLifecycle(
            LlamaServerConfig(
                executable_path=executable,
                model_path=model,
                port=19101,
                log_path=root / "server.log",
            )
        )
        lifecycle._process = FakeProcess()
        lifecycle._resolved_port = 19101
        lifecycle._state = ModelLifecycleState.READY
        return lifecycle

    def chunk(
        self,
        *,
        chunk_id="chunk-1",
        content="same content",
        source_sha="a" * 64,
    ):
        return Chunk(
            chunk_id=chunk_id,
            document_id="doc-1",
            content=content,
            metadata=SourceMetadata(
                project_id="project",
                source_type=SourceType.DOCUMENTATION,
                path="docs/readme.md",
                sha256=source_sha,
            ),
        )

    def opener(self, vectors, calls):
        queue = list(vectors)

        def open_request(request, timeout):
            calls.append(
                json.loads(
                    request.data.decode("utf-8")
                )
            )
            payload = {
                "data": [
                    {
                        "index": 0,
                        "embedding": queue.pop(0),
                    }
                ]
            }
            return FakeResponse(
                json.dumps(payload).encode("utf-8")
            )

        return open_request

    def test_chunk_sha256_uses_exact_utf8_content(self):
        self.assertEqual(
            chunk_content_sha256("olá\n"),
            hashlib.sha256(
                "olá\n".encode("utf-8")
            ).hexdigest(),
        )

    def test_cache_namespace_is_stable_sha256(self):
        self.assertEqual(
            len(TEXT_EMBEDDING_CACHE_NAMESPACE),
            64,
        )
        int(
            TEXT_EMBEDDING_CACHE_NAMESPACE,
            16,
        )

    def test_resolve_path_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Local"
            path = resolve_text_embedding_cache_path(
                local_app_data=root,
            )
            self.assertEqual(
                path,
                root
                / "CodeBridge"
                / "cache"
                / "rag"
                / DEFAULT_TEXT_EMBEDDING_CACHE_FILENAME,
            )
            self.assertFalse(root.exists())

    def test_schema_is_explicit_and_separate_from_fts(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)

        version = initialize_text_embedding_cache(
            connection
        )
        self.assertEqual(
            version,
            TEXT_EMBEDDING_CACHE_SCHEMA_VERSION,
        )
        tables = connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        rendered = "\n".join(
            f"{name}:{sql or ''}"
            for name, sql in tables
        ).lower()
        self.assertIn(
            TEXT_EMBEDDING_CACHE_TABLE,
            rendered,
        )
        self.assertNotIn(
            "virtual table",
            rendered,
        )
        self.assertNotIn("fts5", rendered)
        self.assertNotIn("hnsw", rendered)
        self.assertNotIn("qdrant", rendered)

    def test_unknown_cache_schema_version_is_rejected(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute(
            "PRAGMA user_version = 99"
        )

        with self.assertRaises(
            TextEmbeddingCacheVersionError
        ):
            initialize_text_embedding_cache(
                connection
            )

    def test_vector_roundtrip_preserves_float64_exactly(self):
        connection = connect_text_embedding_cache(
            ":memory:"
        )
        self.addCleanup(connection.close)
        cache = TextEmbeddingCache(connection)
        values = tuple(
            1.0 if index == 7 else index / 100000.0
            for index in range(
                TEXT_EMBEDDING_DIMENSION
            )
        )
        sha = "b" * 64

        cache.put(
            namespace="namespace",
            chunk_sha256=sha,
            dimension=TEXT_EMBEDDING_DIMENSION,
            values=values,
        )

        self.assertEqual(
            cache.get(
                namespace="namespace",
                chunk_sha256=sha,
                dimension=TEXT_EMBEDDING_DIMENSION,
            ),
            values,
        )

    def test_corrupt_vector_blob_is_rejected(self):
        connection = connect_text_embedding_cache(
            ":memory:"
        )
        self.addCleanup(connection.close)
        cache = TextEmbeddingCache(connection)
        sha = "c" * 64
        cache.put(
            namespace="namespace",
            chunk_sha256=sha,
            dimension=TEXT_EMBEDDING_DIMENSION,
            values=unit_vector(),
        )
        connection.execute(
            f"""
            UPDATE {TEXT_EMBEDDING_CACHE_TABLE}
            SET vector_blob = ?
            WHERE namespace = ?
              AND chunk_sha256 = ?
            """,
            (
                sqlite3.Binary(b"corrupt"),
                "namespace",
                sha,
            ),
        )
        connection.commit()

        with self.assertRaises(
            TextEmbeddingCacheIntegrityError
        ):
            cache.get(
                namespace="namespace",
                chunk_sha256=sha,
                dimension=TEXT_EMBEDDING_DIMENSION,
            )

    def test_first_pass_misses_then_second_pass_hits_without_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            connection = connect_text_embedding_cache(
                ":memory:"
            )
            self.addCleanup(connection.close)
            cache = TextEmbeddingCache(
                connection
            )
            calls = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener(
                    [unit_vector(index=3)],
                    calls,
                ),
            )
            chunk = self.chunk()

            first = client.embed_document_chunks_cached(
                [chunk],
                cache,
            )
            self.assertFalse(first[0].cache_hit)
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                cache.count(
                    namespace=TEXT_EMBEDDING_CACHE_NAMESPACE
                ),
                1,
            )

            unloaded = TextModelLifecycle(
                LlamaServerConfig(
                    executable_path=root / "unused.exe",
                    model_path=root / "unused.gguf",
                    port=19102,
                )
            )
            offline_calls = []

            def no_network(*args, **kwargs):
                offline_calls.append(True)
                raise AssertionError(
                    "endpoint must not be called on cache hit"
                )

            offline_client = TextEmbeddingClient(
                unloaded,
                opener=no_network,
            )
            second = (
                offline_client
                .embed_document_chunks_cached(
                    [chunk],
                    cache,
                )
            )

        self.assertTrue(second[0].cache_hit)
        self.assertEqual(offline_calls, [])
        self.assertEqual(
            first[0].result.embedding.values,
            second[0].result.embedding.values,
        )

    def test_changed_chunk_content_is_a_cache_miss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            connection = connect_text_embedding_cache(
                ":memory:"
            )
            self.addCleanup(connection.close)
            cache = TextEmbeddingCache(
                connection
            )
            calls = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener(
                    [
                        unit_vector(index=1),
                        unit_vector(index=2),
                    ],
                    calls,
                ),
            )

            first = client.embed_document_chunks_cached(
                [
                    self.chunk(
                        content="version one"
                    )
                ],
                cache,
            )
            second = client.embed_document_chunks_cached(
                [
                    self.chunk(
                        content="version two"
                    )
                ],
                cache,
            )

        self.assertFalse(first[0].cache_hit)
        self.assertFalse(second[0].cache_hit)
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(
            first[0].chunk_sha256,
            second[0].chunk_sha256,
        )

    def test_source_sha_change_does_not_invalidate_same_chunk_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            connection = connect_text_embedding_cache(
                ":memory:"
            )
            self.addCleanup(connection.close)
            cache = TextEmbeddingCache(
                connection
            )
            calls = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener(
                    [unit_vector(index=5)],
                    calls,
                ),
            )

            first = client.embed_document_chunks_cached(
                [
                    self.chunk(
                        chunk_id="chunk-a",
                        source_sha="a" * 64,
                    )
                ],
                cache,
            )
            second = client.embed_document_chunks_cached(
                [
                    self.chunk(
                        chunk_id="chunk-b",
                        source_sha="b" * 64,
                    )
                ],
                cache,
            )

        self.assertFalse(first[0].cache_hit)
        self.assertTrue(second[0].cache_hit)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            first[0].chunk_sha256,
            second[0].chunk_sha256,
        )

    def test_same_content_with_different_chunk_ids_shares_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            connection = connect_text_embedding_cache(
                ":memory:"
            )
            self.addCleanup(connection.close)
            cache = TextEmbeddingCache(
                connection
            )
            calls = []
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener(
                    [unit_vector(index=6)],
                    calls,
                ),
            )

            results = client.embed_document_chunks_cached(
                [
                    self.chunk(
                        chunk_id="chunk-a"
                    ),
                    self.chunk(
                        chunk_id="chunk-b"
                    ),
                ],
                cache,
            )

        self.assertEqual(
            [item.cache_hit for item in results],
            [False, True],
        )
        self.assertEqual(len(calls), 1)

    def test_namespace_change_causes_miss(self):
        connection = connect_text_embedding_cache(
            ":memory:"
        )
        self.addCleanup(connection.close)
        cache = TextEmbeddingCache(connection)
        sha = "d" * 64
        cache.put(
            namespace="model-a",
            chunk_sha256=sha,
            dimension=TEXT_EMBEDDING_DIMENSION,
            values=unit_vector(),
        )

        self.assertIsNone(
            cache.get(
                namespace="model-b",
                chunk_sha256=sha,
                dimension=TEXT_EMBEDDING_DIMENSION,
            )
        )

    def test_cached_result_preserves_current_chunk_identity_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            connection = connect_text_embedding_cache(
                ":memory:"
            )
            self.addCleanup(connection.close)
            cache = TextEmbeddingCache(
                connection
            )
            client = TextEmbeddingClient(
                self.ready_lifecycle(root),
                opener=self.opener(
                    [unit_vector(index=9)],
                    [],
                ),
            )
            first = self.chunk(
                chunk_id="original"
            )
            client.embed_document_chunks_cached(
                [first],
                cache,
            )

            current = self.chunk(
                chunk_id="current"
            )
            result = client.embed_document_chunks_cached(
                [current],
                cache,
            )[0]

        self.assertIsInstance(
            result,
            CachedDocumentChunkEmbedding,
        )
        self.assertTrue(result.cache_hit)
        self.assertEqual(
            result.result.chunk_id,
            "current",
        )
        self.assertEqual(
            result.result.metadata,
            current.metadata,
        )

    def test_cache_delete_namespace_is_explicit(self):
        connection = connect_text_embedding_cache(
            ":memory:"
        )
        self.addCleanup(connection.close)
        cache = TextEmbeddingCache(connection)

        for namespace in (
            "one",
            "two",
        ):
            cache.put(
                namespace=namespace,
                chunk_sha256="e" * 64,
                dimension=TEXT_EMBEDDING_DIMENSION,
                values=unit_vector(),
            )

        self.assertEqual(
            cache.delete_namespace("one"),
            1,
        )
        self.assertEqual(cache.count(), 1)

    def test_file_database_is_created_only_on_explicit_connect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = (
                Path(temp_dir)
                / DEFAULT_TEXT_EMBEDDING_CACHE_FILENAME
            )
            self.assertFalse(path.exists())
            connection = (
                connect_text_embedding_cache(
                    path
                )
            )
            connection.close()
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
