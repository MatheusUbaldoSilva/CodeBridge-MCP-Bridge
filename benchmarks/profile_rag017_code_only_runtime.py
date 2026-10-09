"""Code-only end-to-end smoke with warmed CODE model and Qdrant client."""
import json,time,subprocess
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local

queries=("Where does RAG read the current Git HEAD?","How is provenance attached to files?","What happens if get_context cannot find a chunk?","Where is the worktree stale state computed?","How is Git branch metadata tracked?")
client=open_qdrant_local()
results=[]
ns=search_persistent_semantic.__globals__
try:
 with patch.dict(ns,{"open_qdrant_local":lambda *args,**kwargs:client,"close_qdrant_local":lambda c:None}):
  for number,q in enumerate(queries,1):
   started=time.perf_counter()
   ranked=search_persistent_semantic(SearchQuery(query=q,project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
   duration=(time.perf_counter()-started)*1000
   results.append({"number":number,"latency_ms":duration,"first_paths":[x.metadata.path for x in ranked[:3]]})
   print("CODE_ONLY",number,round(duration,2),flush=True)
finally:
 resident_pool.close()
 close_qdrant_local(client)
out={"sample_count":len(results),"warm_count":max(0,len(results)-1),"measurements":results,"production_gate":"BLOCKED","warning":"diagnostic smoke, same persistent corpus, not independent quality holdout"}
Path(__file__).with_name("rag017_code_only_runtime_smoke.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
