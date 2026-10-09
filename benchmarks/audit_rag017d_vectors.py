"""RAG-017-D inspect vector top-k misses and chunk coverage, no model changes."""
from pathlib import Path
from collections import Counter
import json,sys
root=Path(__file__).resolve().parents[1]
bench=root/"benchmarks"
report=json.loads((bench/"rag017_failure_matrix.json").read_text(encoding="utf-8"))
groups=Counter()
route=Counter()
vectors={}
records=[]
for r in report["queries"]:
    exp=set(r["expected_sources"])
    t=r["text_vector_top10"]
    c=r["code_vector_top10"]
    vector=t if r["route"]=="TEXT" else c if r["route"]=="CODE" else t+c
    hits=bool(exp.intersection(vector))
    distinct=len(set(vector))
    available=len(vector)
    key="expected_in_vector_top10" if hits else "expected_absent_vector_top10"
    groups[key]+=1
    route[(r["route"],key)]+=1
    records.append({"id":r["id"],"route":r["route"],"expected":sorted(exp),"text_top10":t,"code_top10":c,"top10_unique_path_count":distinct,"top10_chunk_count":available,"expected_in_vector":hits,"final_hit":r["first_expected_rank"] is not None})
out={"stage":"RAG-017-D","status":"DIAGNOSTIC","counts":dict(groups),"route_breakdown":{str(k):v for k,v in route.items()},"note":"Top10 chunk-level path lists; source may exist after rank 10; absence here is not proof of embedding quality or non-indexation.","queries":records}
(bench/"rag017d_vector_diagnostic.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k!="queries"},indent=2))
