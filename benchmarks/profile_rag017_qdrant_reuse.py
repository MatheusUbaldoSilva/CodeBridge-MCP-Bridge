"""Benchmark persistent Qdrant client reuse on the same read-only index."""
import json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
client=open_qdrant_local()
queries=["How is Git provenance attached to a source file?","What happens when get_context requests an invalid chunk?","How does the system track the current Git branch?"]
namespace=search_persistent_semantic.__globals__
times=[]
try:
 with patch.dict(namespace,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda c:None}):
  for q in queries:
   t=time.perf_counter()
   result=search_persistent_semantic(SearchQuery(query=q,project_id="codebridge",top_k=10),QueryRoute.TEXT,experimental_cross_route=True,experimental_resident_models=True)
   ms=(time.perf_counter()-t)*1000
   print("REUSED_QDRANT",len(times)+1,round(ms,3),flush=True)
   times.append(ms)
finally:
 resident_pool.close()
 close_qdrant_local(client)
Path(__file__).with_name("rag017_qdrant_reuse_smoke.json").write_text(json.dumps({"sample_count":len(times),"elapsed_ms":times,"gate":"BLOCKED","note":"diagnostic prototype, shared client not production safe"},indent=2)+"\n",encoding="utf-8")
