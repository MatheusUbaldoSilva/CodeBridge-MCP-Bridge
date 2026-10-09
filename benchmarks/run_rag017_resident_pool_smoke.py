"""Opt-in resident Text+Code model timing; always unload at end."""
import json,time
from pathlib import Path
from rag.contracts import SearchQuery
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.resident_models import resident_pool
queries=["How does Git provenance attach to a file?", "What happens when get_context requests a nonexistent chunk?", "How is a Git branch detected?", "Where are source file changes detected?", "How are chunk metadata verified?"]
measure=[]
try:
 for q in queries:
  start=time.perf_counter()
  result=search_persistent_semantic(SearchQuery(query=q,project_id="codebridge",top_k=10),QueryRoute.TEXT,experimental_cross_route=True,experimental_resident_models=True)
  elapsed=(time.perf_counter()-start)*1000
  print("SAMPLE",len(measure)+1,round(elapsed,3),flush=True)
  measure.append({"ms":elapsed,"paths":[x.metadata.path for x in result[:3]]})
finally:
 resident_pool.close()
report={"sample_count":len(measure),"latencies_ms":measure,"classification":"diagnostic only","production_gate":"BLOCKED"}
file=Path(__file__).parent/"rag017_resident_pool_smoke.json"
file.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print("RESULT",json.dumps(report),flush=True)
