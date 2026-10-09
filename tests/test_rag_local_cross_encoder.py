import io
import json
import unittest
from unittest.mock import patch

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.ranking.local_cross_encoder import cross_encoder_rerank, RerankerUnavailable


def candidate(project, index):
    return SearchResult(
        chunk_id=str(index), document_id="doc-"+str(index),
        content="text "+str(index),
        metadata=SourceMetadata(project_id=project, source_type=SourceType.CODE, path=f"src/{index}.py"),
        score=0.1, rank=index+1, retrieval_modes=("VECTOR",), stale=False,
    )


class Response:
    status=200
    def __init__(self, payload):
        self.data=io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.data.read(n)


class RerankerTests(unittest.TestCase):
    def test_reorders_but_never_adds_sources(self):
        values=(candidate("p",0),candidate("p",1))
        response={"results":[{"index":0,"relevance_score":0.2},{"index":1,"relevance_score":0.9}]}
        with patch.dict(cross_encoder_rerank.__globals__, {"urlopen":lambda *a, **k: Response(response)}) as _:
            results=cross_encoder_rerank("test",values)
        self.assertEqual([r.chunk_id for r in results],["1","0"])
        self.assertEqual([r.rank for r in results],[1,2])
    def test_cross_project_blocked_before_network(self):
        with patch("rag.ranking.local_cross_encoder.urlopen") as _:
            with self.assertRaises(ValueError):
                cross_encoder_rerank("test",(candidate("p",0),candidate("q",1)))
    def test_external_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            cross_encoder_rerank("test",(candidate("p",0),),endpoint="http://outside.example/reranking")
    def test_missing_scores_fail_closed(self):
        with patch.dict(cross_encoder_rerank.__globals__, {"urlopen":lambda *a, **k: Response({"results":[]})}):
            with self.assertRaises(RerankerUnavailable):
                cross_encoder_rerank("test",(candidate("p",0),))
    def test_duplicate_indices_fail_closed(self):
        payload={"results":[{"index":0,"relevance_score":0.7},{"index":0,"relevance_score":0.6}]}
        with patch.dict(cross_encoder_rerank.__globals__, {"urlopen":lambda *a, **k: Response(payload)}):
            with self.assertRaises(RerankerUnavailable):
                cross_encoder_rerank("test",(candidate("p",0),candidate("p",1)))
    def test_unavailable_model_fails_closed(self):
        with patch.dict(cross_encoder_rerank.__globals__, {"urlopen":lambda *a, **k: (_ for _ in ()).throw(OSError("not running"))}):
            with self.assertRaises(RerankerUnavailable):
                cross_encoder_rerank("test",(candidate("p",0),))
