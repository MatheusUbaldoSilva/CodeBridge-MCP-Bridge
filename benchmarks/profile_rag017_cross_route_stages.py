"""Measure actual stage durations on the opt-in persistent cross-route search.

Runs the existing executor with temporary, scoped instrumentation, restoring all
original callables after the benchmark. No modification to production behavior.
"""
import json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool

stages={}
calls={}
namespace=search_persistent_semantic.__globals__
names=("build_rag_status","resolve_rag_sqlite_path","resolve_qdrant_local_path",
       "open_qdrant_local","search_lexical_ranked","search_text_vector",
       "search_code_vector","rerank_documents")
def wrap(name, original):
    def measured(*args,**kwargs):
        start=time.perf_counter()
        try:
            return original(*args,**kwargs)
        finally:
            elapsed=(time.perf_counter()-start)*1000
            stages[name]=stages.get(name,0)+elapsed
            calls[name]=calls.get(name,0)+1
    return measured
text_original=resident_pool.embed_text
code_original=resident_pool.embed_code
queries=["How is Git provenance attached to a source file?",
         "What happens when get_context requests an invalid chunk?",
         "How does the system track the current Git branch?"]
results=[]
try:
    with patch.dict(namespace,{name:wrap(name,namespace[name]) for name in names}),patch.object(resident_pool,"embed_text",wrap("embed_text",text_original)),patch.object(resident_pool,"embed_code",wrap("embed_code",code_original)):
        for q in queries:
            stages.clear()
            calls.clear()
            began=time.perf_counter()
            records=search_persistent_semantic(SearchQuery(query=q,project_id="codebridge",top_k=10),QueryRoute.TEXT,experimental_cross_route=True,experimental_resident_models=True)
            elapsed=(time.perf_counter()-began)*1000
            item={"query":q,"elapsed_ms":elapsed,"stage_ms":dict(stages),"stage_calls":dict(calls),"results":len(records)}
            results.append(item)
            print("PROFILE",json.dumps(item),flush=True)
finally:
    resident_pool.close()
file=Path(__file__).parent/"rag017_cross_route_stage_profile.json"
file.write_text(json.dumps({"sample_count":len(results),"production_gate":"BLOCKED","measurements":results},indent=2)+"\n",encoding="utf-8")
