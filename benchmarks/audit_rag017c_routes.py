"""RAG-017-C category-level route audit, not an oracle for each query."""
from pathlib import Path
from collections import Counter
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rag.runtime.query_classifier import classify_query
bench=ROOT/"benchmarks"
dataset=[json.loads(x) for x in (bench/"rag014_dataset.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
trace=json.loads((bench/"rag017_component_trace.json").read_text(encoding="utf-8"))
rows=[]
for row in dataset:
    actual=classify_query(row["query"])
    before=trace[row["id"]]["route"]
    rows.append({"id":row["id"],"category":row["category"],"old_route":before,"new_route":actual.route.value,"changed":before!=actual.route.value,"reasons":list(actual.reasons)})
out={"stage":"RAG-017-C","queries":rows,"route_counts_before":dict(Counter(x["old_route"] for x in rows)),"route_counts_after":dict(Counter(x["new_route"] for x in rows)),"route_changes":sum(x["changed"] for x in rows),"category_route_counts":{c:dict(Counter(x["new_route"] for x in rows if x["category"]==c)) for c in sorted(set(x["category"] for x in rows))},"note":"Dataset category is coarse metadata, not ground truth route. Cannot infer semantic recall delta without full replay."}
(bench/"rag017c_route_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k!="queries"},indent=2))
