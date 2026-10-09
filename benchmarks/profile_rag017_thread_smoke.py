import concurrent.futures,json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local

client=open_qdrant_local()
def run(text):
 start=time.perf_counter()
 hits=search_persistent_semantic(SearchQuery(query=text,project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
 return {"ms":round((time.perf_counter()-start)*1000,2),"count":len(hits)}
q=["Where is Git HEAD stored?","How is document indexing performed?","Where are project paths validated?"]
try:
 with patch.dict(search_persistent_semantic.__globals__,{"open_qdrant_local":lambda *a,**k:client,"close_qdrant_local":lambda c:None}):
  warm=run(q[0])
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
   results=list(executor.map(run,q[1:]))
finally:
 resident_pool.close()
 close_qdrant_local(client)
report={"warmup":warm,"concurrent":results,"status":"experimental"}
Path(__file__).with_name("rag017_code_only_thread_smoke.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report),flush=True)
