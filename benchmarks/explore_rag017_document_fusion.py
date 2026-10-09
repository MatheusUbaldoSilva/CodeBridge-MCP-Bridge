"""Evaluate general document-level RRF on a fixed persistent corpus.

Diagnostic only. No production writes. Uses semantic + lexical ranked candidates.
"""
import json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
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
conn=sqlite3.connect(f"{resolve_rag_sqlite_path().resolve().as_uri()}?mode=ro",uri=True);client=open_qdrant_local()
cases=[]
try:
 for n,row in enumerate(rows,1):
  route=classify_query(row["query"]).route
  query=SearchQuery(query=row["query"],project_id="codebridge",top_k=32)
  if route==QueryRoute.TEXT:
   c=collect_text_hybrid_candidates(conn,client,query,tv[row["id"]]);lists=(c.lexical,c.vector)
  elif route==QueryRoute.CODE:
   c=collect_code_hybrid_candidates(conn,client,query,cv[row["id"]]);lists=(c.lexical,c.vector)
  else:
   c=collect_hybrid_query_candidates(conn,client,query,route=QueryRoute.HYBRID,text_query_vector=tv[row["id"]],code_query_vector=cv[row["id"]]);lists=(c.lexical,c.text_vector,c.code_vector)
  cases.append((row,lists))
  if n%25==0:print("COLLECT",n,flush=True)
finally:conn.close();close_qdrant_local(client)
def metric(rankings):
 ranks=[next((i for i,path in enumerate(paths[:10],1) if path in truth[row["id"]]),None) for row,paths in zip(rows,rankings)]
 return {"recall5":sum(r is not None and r<=5 for r in ranks)/100,"recall10":sum(r is not None for r in ranks)/100,"mrr":round(sum(1/r for r in ranks if r)/100,6)}
out={}
for k in (5,10,15,20,30,60,120):
 for mode in ("max","sum_decay","reciprocal","chunk_rrf"):
  ranks=[]
  for row,lists in cases:
   if mode=="chunk_rrf":
    fused=reciprocal_rank_fusion(lists,k=k,top_k=96)
    items=deduplicate_ranked_results(fused,top_k=96).results
    paths=list(dict.fromkeys(x.metadata.path for x in items))
   else:
    sums={};representatives={}
    for source in lists:
     for pos,item in enumerate(source,1):
      path=item.metadata.path
      representatives.setdefault(path,item)
      contribution=1/(k+pos)
      if mode=="max":sums[path]=max(sums.get(path,0),contribution)
      elif mode=="reciprocal":sums[path]=sums.get(path,0)+contribution
      else:sums[path]=sums.get(path,0)+contribution/(1+sum(1 for z in source[:pos-1] if z.metadata.path==path))
    paths=sorted(sums,key=lambda p:(-sums[p],p))
   ranks.append(paths[:10])
  out[f"{mode}_k{k}"]=metric(ranks)
  print("SCORE",mode,k,out[f"{mode}_k{k}"],flush=True)
(B/"rag017_document_fusion_ablation.json").write_text(json.dumps({"method":"diagnostic document-level aggregation on frozen queries and persistent corpus","results":out},indent=2)+"\n",encoding="utf-8")
