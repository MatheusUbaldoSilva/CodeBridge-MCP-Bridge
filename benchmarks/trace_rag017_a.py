"""Capture per-stage RAG-014 retrieval evidence without editing retrieval algorithms."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
src=ROOT/"benchmarks"/"run_rag014_semantic_benchmark.py"
spec=importlib.util.spec_from_file_location("rag014_runner_trace",str(src))
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
module.OUTPUT=ROOT/"benchmarks"/"rag017_replay_latest.json"
trace={}
active=[None]
def paths(items):
    return [x.metadata.path or "" for x in items]
def collector(name, old):
    def traced(*args,**kwargs):
        c=old(*args,**kwargs)
        entry=trace[active[0]]
        entry["lexical_top10"]=paths(c.lexical)[:10]
        if hasattr(c,"vector"):
            entry["text_vector_top10" if name=="text" else "code_vector_top10"]=paths(c.vector)[:10]
        else:
            entry["text_vector_top10"]=paths(c.text_vector)[:10]
            entry["code_vector_top10"]=paths(c.code_vector)[:10]
        return c
    return traced
for name, attr in [("text","collect_text_hybrid_candidates"),("code","collect_code_hybrid_candidates"),("hybrid","collect_hybrid_query_candidates")]:
    setattr(module,attr,collector(name,getattr(module,attr)))
old_rrf=module.reciprocal_rank_fusion
def wrapped_rrf(*args,**kwargs):
    out=old_rrf(*args,**kwargs)
    trace[active[0]]["rrf_top10"]=paths(out)[:10]
    return out
module.reciprocal_rank_fusion=wrapped_rrf
old_rank=module._rank_query
def wrapped_rank(*args,**kwargs):
    row=args[2]
    qid=row["id"]
    active[0]=qid
    trace[qid]={"route":module.classify_query(row["query"]).route.value,"lexical_top10":[],"text_vector_top10":[],"code_vector_top10":[],"rrf_top10":[]}
    route, result=old_rank(*args,**kwargs)
    trace[qid]["final_top10"]=paths(result)
    return route,result
module._rank_query=wrapped_rank
try:
    module.main()
finally:
    if trace:
        (ROOT/"benchmarks"/"rag017_component_trace.json").write_text(json.dumps(trace,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("TRACE_SAVED",len(trace),flush=True)
