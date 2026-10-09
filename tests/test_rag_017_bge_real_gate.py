"""RAG-017 cross-encoder empirical gate and bounded input regression."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from rag.contracts import SearchResult, SourceMetadata, SourceType
from rag.ranking.local_cross_encoder import cross_encoder_rerank

B = Path(__file__).resolve().parents[1] / "benchmarks"

class RealRerankerAudit(unittest.TestCase):
    def test_frozen_thresholds_still_block(self):
        record=json.loads((B/"rag017_cross_encoder_real_evaluation.json").read_text(encoding="utf-8"))
        frozen=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))["decision"]["thresholds"]
        self.assertEqual(record["sample"],100)
        self.assertFalse(record["independent_holdout"])
        self.assertEqual(record["production_gate"],"BLOCKED")
        for name,field in (("recall_at_5","recall_at_5_min"),("recall_at_10","recall_at_10_min"),("mrr","mrr_min")):
            self.assertEqual(record["frozen_thresholds"][field], frozen[field])
            self.assertLess(record["reranked"][name],frozen[field])
        self.assertGreater(record["rerank_latency_p95_ms"],0)
    def test_candidate_content_is_bounded(self):
        result=SearchResult(chunk_id="c",document_id="d",content="Z"*10000,
            metadata=SourceMetadata(project_id="p",source_type=SourceType.CODE,path="a.py"),
            score=0.3,rank=1,retrieval_modes=("VECTOR",),stale=False)
        class Reply:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,maxlen):return b'{"results":[{"index":0,"relevance_score":2.3}]}'
        requests=[]
        def simulated_open(req,timeout):
            requests.append(req)
            return Reply()
        with patch.dict(cross_encoder_rerank.__globals__,{"urlopen":simulated_open}):
            output=cross_encoder_rerank("query",(result,))
        self.assertEqual(len(output),1)
        payload=json.loads(requests[0].data)
        self.assertEqual(len(payload["documents"][0]),1400)
