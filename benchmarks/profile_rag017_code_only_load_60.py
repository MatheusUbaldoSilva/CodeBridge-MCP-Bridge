"""Read-only warm load test: CODE-only resident model and persistent Qdrant."""
import concurrent.futures,json,math,statistics,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
prompts=[
 "Where is a Git branch derived from HEAD?",
 "How are indexed sources filtered by project?",
 "Which code detects stale document provenance?",
 "How does document ranking combine chunk results?",
 "Find the module responsible for embedding code queries.",
 "How does the index update files incrementally?",
 "What validates a requested source path?",
 "Where is the persistent vector index opened?"]
client=open_qdrant_local()
ns=search_persistent_semantic.__globals__
def search(n):
 start=time.perf_counter()
 hits=search_persistent_semantic(SearchQuery(query=prompts[n%len(prompts)]+f" Reference request {n}.",project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
 return {"ms":round((time.perf_counter()-start)*1000,3),"count":len(hits)}
runs=[]
try:
 with patch.dict(ns,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda x:None}):
  cold=search(0)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
   for i in range(0,60,3):
    batch=list(executor.map(search,range(i+1,i+4)))
    runs.extend(batch)
    if i%15==0:print("BATCH",i+3,flush=True)
finally:
 resident_pool.close();close_qdrant_local(client)
ordered=sorted(x["ms"] for x in runs)
out={"cold_ms":cold["ms"],"warm_count":len(runs),"workers":3,"warm_p95_ms":ordered[math.ceil(len(ordered)*.95)-1],"warm_max_ms":ordered[-1],"warm_median_ms":statistics.median(ordered),"all_count_10":all(x["count"]==10 for x in runs),"production_gate":"BLOCKED","remark":"60 warm measurements in one process on shared local Qdrant, repeated query templates, not independent quality holdout"}
Path(__file__).with_name("rag017_code_only_load_60.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf8")
print("SUMMARY",json.dumps(out),flush=True)
