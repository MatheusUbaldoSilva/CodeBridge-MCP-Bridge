import math
import unittest

from rag.contracts import Chunk, SourceMetadata, SourceType
from rag.models.code_backend_policy import CodeRetrievalTask
from rag.models.code_embedding import (
    CODE_EMBEDDING_DIMENSION,
    CodeChunkEmbedding,
    CodeEmbeddingRole,
    CodeEmbeddingVector,
)
from rag.retrieval.code_semantic import retrieve_nl_to_code
from rag.ranking.code_similarity import (
    CODE_NL_RETRIEVAL_MODE,
    CODE_NL_TASK_MODE,
    rank_nl_to_code,
)


def vector_with_cosine(score):
    if not -1.0 <= score <= 1.0:
        raise ValueError
    values = [0.0] * CODE_EMBEDDING_DIMENSION
    values[0] = score
    values[1] = math.sqrt(max(0.0, 1.0 - score * score))
    return tuple(values)


def query_vector():
    values = [0.0] * CODE_EMBEDDING_DIMENSION
    values[0] = 1.0
    return tuple(values)


def chunk(chunk_id, path, symbol, line, content=None):
    return Chunk(
        chunk_id,
        "doc-" + chunk_id,
        content or f"code for {symbol}",
        SourceMetadata(
            "codebridge",
            SourceType.CODE,
            path=path,
            symbol=symbol,
            line_start=line,
            line_end=line + 2,
            sha256=(chunk_id[0] if chunk_id[0] in "abcdef" else "a") * 64,
        ),
    )


def embedded(item, score):
    return CodeChunkEmbedding(
        chunk_id=item.chunk_id,
        document_id=item.document_id,
        metadata=item.metadata,
        task=CodeRetrievalTask.NL2CODE,
        embedding=CodeEmbeddingVector(
            task=CodeRetrievalTask.NL2CODE,
            role=CodeEmbeddingRole.PASSAGE,
            values=vector_with_cosine(score),
        ),
    )


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def embed_query(self, task, text):
        self.calls.append(("query", task, text))
        return CodeEmbeddingVector(
            task=task,
            role=CodeEmbeddingRole.QUERY,
            values=query_vector(),
        )

    def embed_code_chunks(self, chunks, *, task=CodeRetrievalTask.NL2CODE):
        items = tuple(chunks)
        self.calls.append(("chunks", task, tuple(x.chunk_id for x in items)))
        return tuple(
            embedded(item, self.mapping[item.chunk_id])
            for item in items
        )


class RagCodeNlRetrievalTests(unittest.TestCase):
    def test_ranking_places_highest_cosine_first(self):
        chunks = (
            chunk("a-owner", "src/item.cpp", "CanMoveItem", 120),
            chunk("b-cancel", "src/runtime.py", "cancel_current", 300),
            chunk("c-wait", "author_mcp/mcp_server.py", "codebridge_wait", 976),
        )
        query = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        ranked = rank_nl_to_code(
            query,
            chunks,
            (
                embedded(chunks[0], 0.91),
                embedded(chunks[1], 0.42),
                embedded(chunks[2], 0.61),
            ),
            top_k=3,
        )
        self.assertEqual(
            [item.chunk_id for item in ranked],
            ["a-owner", "c-wait", "b-cancel"],
        )
        self.assertEqual(
            [item.rank for item in ranked],
            [1, 2, 3],
        )
        self.assertAlmostEqual(ranked[0].score, 0.91)

    def test_retrieval_uses_nl2code_query_and_passages(self):
        chunks = (
            chunk("a-owner", "src/item.cpp", "CanMoveItem", 120),
            chunk("b-cancel", "src/runtime.py", "cancel_current", 300),
        )
        client = FakeClient(
            {
                "a-owner": 0.93,
                "b-cancel": 0.40,
            }
        )
        results = retrieve_nl_to_code(
            client,
            "onde valida ownership do item?",
            chunks,
            top_k=1,
        )
        self.assertEqual(results[0].chunk_id, "a-owner")
        self.assertEqual(
            client.calls[0],
            (
                "query",
                CodeRetrievalTask.NL2CODE,
                "onde valida ownership do item?",
            ),
        )
        self.assertEqual(
            client.calls[1][1],
            CodeRetrievalTask.NL2CODE,
        )

    def test_search_result_preserves_source_for_real_verification(self):
        item = chunk(
            "c-wait",
            "author_mcp/mcp_server.py",
            "codebridge_wait",
            976,
            "def codebridge_wait(...): pass",
        )
        result = retrieve_nl_to_code(
            FakeClient({"c-wait": 0.88}),
            "onde o runtime acorda o wait?",
            [item],
            top_k=1,
        )[0]
        self.assertEqual(result.content, item.content)
        self.assertEqual(result.metadata, item.metadata)
        self.assertFalse(result.stale)
        self.assertEqual(
            result.retrieval_modes,
            (
                CODE_NL_RETRIEVAL_MODE,
                CODE_NL_TASK_MODE,
            ),
        )

    def test_top_k_is_enforced(self):
        items = tuple(
            chunk(
                f"{letter}-x",
                f"src/{letter}.py",
                f"f_{letter}",
                index + 1,
            )
            for index, letter in enumerate("abc")
        )
        results = retrieve_nl_to_code(
            FakeClient(
                {
                    "a-x": 0.9,
                    "b-x": 0.8,
                    "c-x": 0.7,
                }
            ),
            "query",
            items,
            top_k=2,
        )
        self.assertEqual(len(results), 2)

    def test_ties_have_deterministic_source_order(self):
        first = chunk("b-tie", "src/z.py", "z", 20)
        second = chunk("a-tie", "src/a.py", "a", 10)
        query = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        results = rank_nl_to_code(
            query,
            (first, second),
            (
                embedded(first, 0.75),
                embedded(second, 0.75),
            ),
            top_k=2,
        )
        self.assertEqual(
            [item.chunk_id for item in results],
            ["a-tie", "b-tie"],
        )

    def test_duplicate_chunk_ids_are_rejected(self):
        first = chunk("a-dup", "src/a.py", "a", 1)
        duplicate = Chunk(
            "a-dup",
            "doc-other",
            "other",
            SourceMetadata(
                "codebridge",
                SourceType.CODE,
                path="src/b.py",
            ),
        )
        query = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        with self.assertRaises(ValueError):
            rank_nl_to_code(
                query,
                (first, duplicate),
                (
                    embedded(first, 0.8),
                    CodeChunkEmbedding(
                        duplicate.chunk_id,
                        duplicate.document_id,
                        duplicate.metadata,
                        CodeRetrievalTask.NL2CODE,
                        CodeEmbeddingVector(
                            CodeRetrievalTask.NL2CODE,
                            CodeEmbeddingRole.PASSAGE,
                            vector_with_cosine(0.7),
                        ),
                    ),
                ),
                top_k=2,
            )

    def test_non_code_corpus_is_rejected_before_model_call(self):
        bad = Chunk(
            "doc",
            "d",
            "text",
            SourceMetadata(
                "codebridge",
                SourceType.DOCUMENTATION,
                path="docs/readme.md",
            ),
        )
        client = FakeClient({})
        with self.assertRaises(ValueError):
            retrieve_nl_to_code(
                client,
                "query",
                [bad],
            )
        self.assertEqual(client.calls, [])

    def test_empty_corpus_returns_without_model_call(self):
        client = FakeClient({})
        self.assertEqual(
            retrieve_nl_to_code(
                client,
                "query",
                (),
            ),
            (),
        )
        self.assertEqual(client.calls, [])

    def test_invalid_top_k_and_query_are_rejected(self):
        client = FakeClient({})
        with self.assertRaises(ValueError):
            retrieve_nl_to_code(client, "", (), top_k=1)
        with self.assertRaises(ValueError):
            retrieve_nl_to_code(client, "x", (), top_k=0)

    def test_module_does_not_persist_or_import_vector_store(self):
        import inspect
        import rag.retrieval.code_semantic as retrieval
        import rag.ranking.code_similarity as ranking

        source = (
            inspect.getsource(retrieval)
            + inspect.getsource(ranking)
        ).lower()
        self.assertNotIn("qdrant", source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("hnsw", source)
        self.assertNotIn("create table", source)


if __name__ == "__main__":
    unittest.main()
