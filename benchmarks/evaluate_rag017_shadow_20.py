"""Additional source-grounded diagnostic, not a certified independent holdout."""
import json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
root=Path(__file__).parent
cases=[json.loads(line) for line in (root/"rag017_shadow_20_queries.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]
client=open_qdrant_local()
data=[]
try:
 with patch.dict(search_persistent_semantic.__globals__,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda x:None}):
  for row in cases:
   start=time.perf_counter()
   found=search_persistent_semantic(SearchQuery(query=row["query"],project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
   latency=(time.perf_counter()-start)*1000
   rank=next((i for i,item in enumerate(found,1) if item.metadata.path in row["expected_paths"]),None)
   data.append({"id":row["id"],"rank":rank,"latency_ms":round(latency,3)})
   print("CASE",row["id"],rank,round(latency,2),flush=True)
finally:
 resident_pool.close()
 close_qdrant_local(client)
n=len(data)
report={"sample_count":n,"recall_at_5":sum(x["rank"] is not None and x["rank"]<=5 for x in data)/n,"recall_at_10":sum(x["rank"] is not None for x in data)/n,"mrr":sum(1/x["rank"] for x in data if x["rank"] is not None)/n,"results":data,"independent_holdout":False,"annotation_note":"assistant-generated source-grounded shadow examples, not a pre-registered independent evaluator","gate":"BLOCKED"}
(root/"rag017_shadow_20_results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
print("SUMMARY",json.dumps({k:v for k,v in report.items() if k!="results"}),flush=True)
