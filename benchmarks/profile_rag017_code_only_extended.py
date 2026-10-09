"""Independent smoke prompts not used in RAG-014 ground truth.
These test runtime behavior only; they are not a validated quality holdout.
"""
import json,time,math,subprocess
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local

queries=[
 "Identify the function that normalizes CodeBridge search path restrictions",
 "Explain which part of the indexing service stores incremental update state",
 "Locate the function responsible for resolving the current active Git commit",
 "What validates chunk line offsets before writing the retrieval index?",
 "How are source paths checked to stop directory traversal?",
 "Find the code that verifies a model artifact checksum",
 "Describe how RAG changes its stale marker after Git modifications",
 "Where does the system enforce project isolation for search inputs?",
 "Explain how the text model handles model server lifecycle cleanup",
 "Which code determines the vector embedding task for natural language queries",
 "How does the document reranker aggregate chunks from the same file?",
 "Locate the component that opens the local vector database"]
client=open_qdrant_local()
ns=search_persistent_semantic.__globals__
results=[]
try:
 with patch.dict(ns,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda c:None}):
  for n,q in enumerate(queries):
   start=time.perf_counter()
   matches=search_persistent_semantic(SearchQuery(query=q,project_id="codebridge",top_k=10),QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
   elapsed=(time.perf_counter()-start)*1000
   results.append({"elapsed_ms":elapsed,"top1":matches[0].metadata.path if matches else None})
   print("SMOKE",n+1,round(elapsed,2),flush=True)
finally:
 resident_pool.close()
 close_qdrant_local(client)
warm=sorted(x["elapsed_ms"] for x in results[1:])
result={"sample":len(results),"warm_sample":len(warm),"warm_max_ms":max(warm),"warm_p95_observed_ms":warm[math.ceil(.95*len(warm))-1],"results":results,"production_gate":"BLOCKED","reason":"smoke sample, no independent quality labels or concurrent peak measurement"}
Path(__file__).with_name("rag017_code_only_extended_smoke.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print("SUMMARY",json.dumps({k:v for k,v in result.items() if k!="results"}),flush=True)
