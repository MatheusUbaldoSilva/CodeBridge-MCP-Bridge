"""Controlled retrieval ablation on ONE persistent corpus (100 frozen queries).

No writes to production; compare candidate depth and file diversity on same corpus.
"""
from __future__ import annotations
import json, sqlite3, sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import classify_query,QueryRoute
from rag.runtime.status import resolve_rag_sqlite_path
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.retrieval.hybrid_text import collect_text_hybrid_candidates
from rag.retrieval.hybrid_code import collect_code_hybrid_candidates
from rag.retrieval.hybrid_query import collect_hybrid_query_candidates
from rag.ranking.rrf import reciprocal_rank_fusion
from rag.ranking.dedup import deduplicate_ranked_results
import importlib.util
spec=importlib.util.spec_from_file_location("rag014",ROOT/"benchmarks"/"run_rag014_semantic_benchmark.py")
runner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=runner;spec.loader.exec_module(runner)

B=ROOT/"benchmarks"
rows=[json.loads(s) for s in (B/"rag014_dataset.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
truth={x["id"]:set(x["expected_paths"]) for x in (json.loads(s) for s in (B/"rag014_ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if s.strip())}
print("QUERY_EMBED_TEXT",flush=True)
textvec,*_=runner._embed_text_queries(rows)
print("QUERY_EMBED_CODE",flush=True)
codevec,*_=runner._embed_code_queries(rows)
print("ABLATION_BEGIN",flush=True)
conn=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True)
qdrant=open_qdrant_local()
out={}
try:
    for depth in (10,20,40):
        results={x:[] for x in ("baseline","diverse","deep")}
        for row in rows:
            route=classify_query(row["query"]).route
            q=SearchQuery(query=row["query"],project_id="codebridge",top_k=depth)
            if route==QueryRoute.TEXT:
                c=collect_text_hybrid_candidates(conn,qdrant,q,textvec[row["id"]])
                lists=(c.lexical,c.vector)
            elif route==QueryRoute.CODE:
                c=collect_code_hybrid_candidates(conn,qdrant,q,codevec[row["id"]])
                lists=(c.lexical,c.vector)
            else:
                c=collect_hybrid_query_candidates(conn,qdrant,q,route=QueryRoute.HYBRID,text_query_vector=textvec[row["id"]],code_query_vector=codevec[row["id"]])
                lists=(c.lexical,c.text_vector,c.code_vector)
            fused=reciprocal_rank_fusion(lists,top_k=max(30,depth*3))
            dedup=deduplicate_ranked_results(fused,top_k=depth).results
            unique=[]
            seen=set()
            for x in dedup:
                path=x.metadata.path
                if path not in seen:
                    unique.append(x)
                    seen.add(path)
            results["baseline"].append((row["id"],[x.metadata.path for x in dedup[:10]]))
            results["diverse"].append((row["id"],[x.metadata.path for x in unique[:10]]))
            results["deep"].append((row["id"],[x.metadata.path for x in fused[:10]]))
        def mrr(items):
            ranks=[]
            for k,paths in items:
                rank=next((i for i,p in enumerate(paths,1) if p in truth[k]),None)
                ranks.append(rank)
            return {"recall5":round(sum(bool(r and r<=5) for r in ranks)/100,3),"recall10":round(sum(bool(r) for r in ranks)/100,3),"mrr":round(sum(1/r for r in ranks if r)/100,5)}
        out[str(depth)]={k:mrr(v) for k,v in results.items()}
        print("DEPTH",depth,json.dumps(out[str(depth)]),flush=True)
finally:
    conn.close()
    close_qdrant_local(qdrant)
(B/"rag017_quality_ablation.json").write_text(json.dumps({"notes":"One fixed persistent corpus; no held-out validation. Treat as diagnostic only.","results":out},indent=2)+"\n",encoding="utf-8")
