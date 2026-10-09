"""RAG-017 optional true cross-encoder benchmark on persistent CodeBridge index.

Run only with a trusted local llama.cpp rerank model already running at
127.0.0.1:8081. Never writes production data or declares readiness itself.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
B=ROOT/"benchmarks"

from rag.contracts import SearchQuery
from rag.runtime.query_classifier import classify_query, QueryRoute
from rag.runtime.status import resolve_rag_sqlite_path
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.retrieval.hybrid_text import collect_text_hybrid_candidates
from rag.retrieval.hybrid_code import collect_code_hybrid_candidates
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.ranking.semantic_document_reranker import rerank_documents
from rag.ranking.multi_passage_reranker import rerank_multi_passage

spec=importlib.util.spec_from_file_location("rag017_original_benchmark",B/"run_rag014_semantic_benchmark.py")
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

def load_jsonl(name):
    return [json.loads(line) for line in (B/name).read_text(encoding="utf-8").splitlines() if line.strip()]

def aggregate(paths,truth):
    ranks=[next((i for i,p in enumerate(paths[k][:10],1) if p in truth[k]),None) for k in sorted(truth)]
    return {
        "recall_at_5":sum(r is not None and r<=5 for r in ranks)/len(ranks),
        "recall_at_10":sum(r is not None for r in ranks)/len(ranks),
        "mrr":sum(1/r for r in ranks if r)/len(ranks),
    }

def main():
    dataset=load_jsonl("rag014_dataset.jsonl")
    truth={x["id"]:set(x["expected_paths"]) for x in load_jsonl("rag014_ground_truth.jsonl")}
    assert len(dataset)==len(truth)==100
    # A real model is mandatory; refuse to generate fictitious gate results.
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/health",timeout=2) as response:
            if response.status!=200:
                raise RuntimeError("local reranking model is not healthy")
    except Exception as exc:
        raise RuntimeError("A dedicated local cross-encoder at port 8081 is REQUIRED") from exc
    text_vectors,*_=mod._embed_text_queries(dataset)
    code_vectors,*_=mod._embed_code_queries(dataset)
    db=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True)
    qdrant=open_qdrant_local()
    baseline={}
    reranked={}
    latencies=[]
    try:
        for item in dataset:
            route=classify_query(item["query"]).route
            q=SearchQuery(query=item["query"],project_id="codebridge",top_k=32)
            if route is QueryRoute.TEXT:
                c=collect_text_hybrid_candidates(db,qdrant,q,text_vectors[item["id"]])
                rankings=(c.lexical,c.vector)
            elif route is QueryRoute.CODE:
                c=collect_code_hybrid_candidates(db,qdrant,q,code_vectors[item["id"]])
                rankings=(c.lexical,c.vector)
            else:
                c=collect_hybrid_query_candidates(db,qdrant,q,route=route,text_query_vector=text_vectors[item["id"]],code_query_vector=code_vectors[item["id"]])
                rankings=(c.lexical,c.text_vector,c.code_vector)
            candidates=rerank_documents(rankings,rrf_k=10,top_k=20)
            baseline[item["id"]]=[r.metadata.path for r in candidates[:10]]
            start=time.perf_counter()
            reordered=rerank_multi_passage(item["query"],rankings,top_k=10,documents_limit=20,passages_per_document=3)
            latencies.append((time.perf_counter()-start)*1000)
            reranked[item["id"]]=[r.metadata.path for r in reordered]
    finally:
        db.close()
        close_qdrant_local(qdrant)
    import math
    times=sorted(latencies)
    frozen=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))["decision"]["thresholds"]
    before=aggregate(baseline,truth)
    after=aggregate(reranked,truth)
    out={
        "stage":"RAG-017-multi-passage",
        "sample":100,
        "independent_holdout":False,
        "baseline":before,
        "reranked":after,
        "rerank_latency_p95_ms":times[math.ceil(.95*len(times))-1],
        "frozen_thresholds":frozen,
        "passes_three_quality_metrics":(
            after["recall_at_5"]>=frozen["recall_at_5_min"]
            and after["recall_at_10"]>=frozen["recall_at_10_min"]
            and after["mrr"]>=frozen["mrr_min"]),
        "production_gate":"BLOCKED",
        "caveat":"Exploratory benchmark on known questions; requires independent validation and RAM/VRAM before approval.",
    }
    (B/"rag017_multi_passage_evaluation.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    main()
