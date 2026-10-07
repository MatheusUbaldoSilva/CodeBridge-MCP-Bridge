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
from rag.ranking.code_similarity import (
    CODE_CODE_TASK_MODE,
    CODE_VECTOR_RETRIEVAL_MODE,
    rank_code_to_code,
)
from rag.retrieval.code_semantic import retrieve_code_to_code


def query_vector():
    values = [0.0] * CODE_EMBEDDING_DIMENSION
    values[0] = 1.0
    return tuple(values)


def vector_with_cosine(score):
    values = [0.0] * CODE_EMBEDDING_DIMENSION
    values[0] = score
    values[1] = math.sqrt(max(0.0, 1.0 - score * score))
    return tuple(values)


def chunk(chunk_id, path, symbol, line):
    return Chunk(
        chunk_id,
        "doc-" + chunk_id,
        f"code for {symbol}",
        SourceMetadata(
            "codebridge",
            SourceType.CODE,
            path=path,
            symbol=symbol,
            line_start=line,
            line_end=line + 2,
            sha256="a" * 64,
        ),
    )


def embedded(item, score):
    return CodeChunkEmbedding(
        item.chunk_id,
        item.document_id,
        item.metadata,
        CodeRetrievalTask.CODE2CODE,
        CodeEmbeddingVector(
            CodeRetrievalTask.CODE2CODE,
            CodeEmbeddingRole.PASSAGE,
            vector_with_cosine(score),
        ),
    )


class FakeClient:
    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def embed_query(self, task, text):
        self.calls.append(("query", task, text))
        return CodeEmbeddingVector(
            task,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )

    def embed_code_chunks(self, chunks, *, task=CodeRetrievalTask.NL2CODE):
        items = tuple(chunks)
        self.calls.append(("chunks", task, tuple(x.chunk_id for x in items)))
        return tuple(
            embedded(item, self.scores[item.chunk_id])
            for item in items
        )


class RagCodeToCodeRetrievalTests(unittest.TestCase):
    def test_code2code_task_is_used_for_query_and_passages(self):
        items = (
            chunk("wait", "author_mcp/mcp_server.py", "codebridge_wait", 967),
            chunk("cancel", "app/runtime.py", "cancel_current", 300),
        )
        client = FakeClient({"wait": 0.91, "cancel": 0.40})
        results = retrieve_code_to_code(
            client,
            'result = _safe_exchange("EXECUTION_V2_WAIT", payload)',
            items,
            top_k=1,
        )
        self.assertEqual(results[0].chunk_id, "wait")
        self.assertEqual(client.calls[0][1], CodeRetrievalTask.CODE2CODE)
        self.assertEqual(client.calls[1][1], CodeRetrievalTask.CODE2CODE)

    def test_code2code_result_mode_is_explicit(self):
        item = chunk("cancel", "app/runtime.py", "cancel_current", 300)
        result = retrieve_code_to_code(
            FakeClient({"cancel": 0.88}),
            "self._cancel_requested = True",
            [item],
            top_k=1,
        )[0]
        self.assertEqual(
            result.retrieval_modes,
            (
                CODE_VECTOR_RETRIEVAL_MODE,
                CODE_CODE_TASK_MODE,
            ),
        )

    def test_code2code_ranking_uses_cosine_descending(self):
        items = (
            chunk("a", "src/a.py", "a", 1),
            chunk("b", "src/b.py", "b", 2),
            chunk("c", "src/c.py", "c", 3),
        )
        query = CodeEmbeddingVector(
            CodeRetrievalTask.CODE2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        results = rank_code_to_code(
            query,
            items,
            (
                embedded(items[0], 0.20),
                embedded(items[1], 0.95),
                embedded(items[2], 0.60),
            ),
            top_k=3,
        )
        self.assertEqual(
            [result.chunk_id for result in results],
            ["b", "c", "a"],
        )

    def test_nl2code_query_embedding_is_rejected_by_code2code_ranker(self):
        item = chunk("a", "src/a.py", "a", 1)
        query = CodeEmbeddingVector(
            CodeRetrievalTask.NL2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        with self.assertRaises(ValueError):
            rank_code_to_code(
                query,
                [item],
                [embedded(item, 0.9)],
                top_k=1,
            )

    def test_non_code_source_is_rejected_before_model_call(self):
        bad = Chunk(
            "doc",
            "doc-doc",
            "text",
            SourceMetadata(
                "codebridge",
                SourceType.DOCUMENTATION,
                path="docs/a.md",
            ),
        )
        client = FakeClient({})
        with self.assertRaises(ValueError):
            retrieve_code_to_code(client, "x = 1", [bad])
        self.assertEqual(client.calls, [])

    def test_empty_corpus_does_not_load_embeddings(self):
        client = FakeClient({})
        self.assertEqual(
            retrieve_code_to_code(client, "x = 1", ()),
            (),
        )
        self.assertEqual(client.calls, [])

    def test_invalid_query_and_top_k_are_rejected(self):
        client = FakeClient({})
        with self.assertRaises(ValueError):
            retrieve_code_to_code(client, "", ())
        with self.assertRaises(ValueError):
            retrieve_code_to_code(client, "x = 1", (), top_k=0)

    def test_provenance_is_preserved(self):
        item = chunk(
            "wait",
            "author_mcp/mcp_server.py",
            "codebridge_wait",
            967,
        )
        result = retrieve_code_to_code(
            FakeClient({"wait": 0.90}),
            "_safe_exchange('EXECUTION_V2_WAIT', payload)",
            [item],
            top_k=1,
        )[0]
        self.assertEqual(result.metadata, item.metadata)
        self.assertEqual(result.content, item.content)
        self.assertFalse(result.stale)

    def test_tie_break_remains_deterministic(self):
        z = chunk("z", "src/z.py", "z", 10)
        a = chunk("a", "src/a.py", "a", 20)
        query = CodeEmbeddingVector(
            CodeRetrievalTask.CODE2CODE,
            CodeEmbeddingRole.QUERY,
            query_vector(),
        )
        results = rank_code_to_code(
            query,
            (z, a),
            (embedded(z, 0.8), embedded(a, 0.8)),
            top_k=2,
        )
        self.assertEqual(
            [result.chunk_id for result in results],
            ["a", "z"],
        )

    def test_no_vector_store_is_introduced(self):
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


if __name__ == "__main__":
    unittest.main()
