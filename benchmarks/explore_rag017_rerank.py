"""Diagnostic ablation: candidate diversity with query-aware lexical overlap.

Exploratory only: no training, no changes to production. Thresholds immutable.
"""
import json,re,math,sys,sqlite3
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
spec=importlib.util.spec_from_file_location("runner",ROOT/"benchmarks"/"run_rag014_semantic_benchmark.py")
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
B=ROOT/"benchmarks"
rows=[json.loads(x) for x in (B/"rag014_dataset.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
truth={r["id"]:set(r["expected_paths"]) for r in (json.loads(x) for x in (B/"rag014_ground_truth.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
print("EMBED_TEXT",flush=True);tv,*_=mod._embed_text_queries(rows)
print("EMBED_CODE",flush=True);cv,*_=mod._embed_code_queries(rows)
conn=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True)
client=open_qdrant_local()
data=[]
try:
 for idx,row in enumerate(rows):
    route=classify_query(row["query"]).route
    q=SearchQuery(query=row["query"],project_id="codebridge",top_k=32)
    if route==QueryRoute.TEXT:
        c=collect_text_hybrid_candidates(conn,client,q,tv[row["id"]]);lists=(c.lexical,c.vector)
    elif route==QueryRoute.CODE:
        c=collect_code_hybrid_candidates(conn,client,q,cv[row["id"]]);lists=(c.lexical,c.vector)
    else:
        c=collect_hybrid_query_candidates(conn,client,q,route=QueryRoute.HYBRID,text_query_vector=tv[row["id"]],code_query_vector=cv[row["id"]]);lists=(c.lexical,c.text_vector,c.code_vector)
    fused=reciprocal_rank_fusion(lists,top_k=96)
    unique=[];seen=set()
    for x in deduplicate_ranked_results(fused,top_k=96).results:
        if x.metadata.path in seen: continue
        seen.add(x.metadata.path);unique.append(x)
    data.append((row,unique))
    if (idx+1)%25==0:print("COLLECT",idx+1,flush=True)
finally:
 conn.close();close_qdrant_local(client)
stop=set("the this that with from what where which when does have how why was were are for its code file files uma para como onde qual quais quem que por dos das com na nos em do de se uma seu isso is at and".split())
def tok(x):return set(w for w in re.findall(r"\w+",x.casefold()) if len(w)>2 and w not in stop)
def metrics(ranked):
 ranks=[next((i for i,x in enumerate(xs[:10],1) if x.metadata.path in truth[row["id"]]),None) for row,xs in zip(rows,ranked)]
 return {"recall5":sum(bool(r and r<=5) for r in ranks)/100,"recall10":sum(bool(r) for r in ranks)/100,"mrr":sum(1/r for r in ranks if r)/100}
scores={}
for pool in (10,20,32):
 for weight in (0,0.15,0.4,0.8,1.5):
    ranked=[]
    for row,items in data:
        qtokens=tok(row["query"])
        def score(item):
            path=tok(item.metadata.path or "")
            content=tok(item.content[:1500])
            overlap=(2*len(path&qtokens)+len(content&qtokens))/max(1,len(qtokens))
            return item.score + weight*overlap
        cand=items[:pool]
        if weight>0: cand=sorted(cand,key=score,reverse=True)
        ranked.append(cand[:10])
    scores[f"pool{pool}_weight{weight}"]=metrics(ranked)
    print("VARIANT",pool,weight,scores[f"pool{pool}_weight{weight}"],flush=True)
(B/"rag017_quality_rerank_exploration.json").write_text(json.dumps({"scope":"exploratory evaluation on same frozen queries, not independent validation","results":scores},indent=2)+"\n",encoding="utf-8")
