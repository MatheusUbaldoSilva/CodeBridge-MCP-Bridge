"""RAG-017-F frozen-dataset, no-overfit checks and independent gate evaluation."""
from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.benchmark.metrics import evaluate_ranked_paths

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/"benchmarks"
def js(name):
    return json.loads((B/name).read_text(encoding="utf-8"))
def jl(name):
    return [json.loads(x) for x in (B/name).read_text(encoding="utf-8").splitlines() if x.strip()]
dataset=jl("rag014_dataset.jsonl")
truth=jl("rag014_ground_truth.jsonl")
assert len(dataset)==len(truth)==100
ids={r["id"] for r in dataset}
expected={r["id"]:tuple(r["expected_paths"]) for r in truth}
assert ids==set(expected)
ref=js("rag014_readiness_report.json")
run=js("rag017f_semantic_latest.json")
actual=run["top10_paths"]
assert ids==set(actual)
metrics=evaluate_ranked_paths(actual,expected).to_dict()
assert all(abs(metrics[k]-run["metrics"][k])<1e-10 for k in ("recall_at_5","recall_at_10","mrr"))
thresholds=ref["decision"]["thresholds"]
qualifiers={
    "recall_at_5": metrics["recall_at_5"]>=thresholds["recall_at_5_min"],
    "recall_at_10": metrics["recall_at_10"]>=thresholds["recall_at_10_min"],
    "mrr": metrics["mrr"]>=thresholds["mrr_min"],
}
report={
    "stage":"RAG-017-F",
    "benchmark":"real semantic Jina, all 100 frozen queries",
    "metrics":metrics,
    "frozen_reference":ref["semantic_metrics"]["metrics"],
    "thresholds":{k:thresholds[k] for k in ("recall_at_5_min","recall_at_10_min","mrr_min")},
    "qualifiers":qualifiers,
    "quality_gate":"PASS" if all(qualifiers.values()) else "BLOCKED",
    "production_gate":"BLOCKED" if (not all(qualifiers.values()) or ref["production_index"]["state"]!="READY") else "NOT_EVALUATED",
    "production_index_caveat":"Prior report index status; this benchmark uses a temporary index and does not assert current production readiness.",
    "corpus":run["corpus"],
    "reference_corpus":ref["semantic_metrics"]["corpus"],
    "provenance":{"dataset":"benchmarks/rag014_dataset.jsonl","ground_truth":"benchmarks/rag014_ground_truth.jsonl","replay":"benchmarks/rag017f_semantic_latest.json"},
}
(B/"rag017f_regression_gate.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("corpus","reference_corpus","provenance")},indent=2,ensure_ascii=False))
