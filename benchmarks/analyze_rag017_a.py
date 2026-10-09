"""RAG-017-A: read-only analysis of frozen RAG-014 benchmark artifacts."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"
def load(name):
    return json.loads((BENCH / name).read_text(encoding="utf-8"))
def jsonl(name):
    return [json.loads(s) for s in (BENCH / name).read_text(encoding="utf-8").splitlines() if s.strip()]

dataset = jsonl("rag014_dataset.jsonl")
truth = jsonl("rag014_ground_truth.jsonl")
semantic = load("rag014_semantic_benchmark_latest.json")
lexical = load("rag014_lexical_baseline_latest.json")
assert len(dataset) == len(truth) == 100
queries = {r["id"]: r for r in dataset}
expected = {r["id"]: r["expected_paths"] for r in truth}
ranked = semantic["top10_paths"]
assert set(queries) == set(expected) == set(ranked)
rows = []
for qid in sorted(queries):
    tops = ranked[qid]
    exp = expected[qid]
    rank = next((i for i, path in enumerate(tops, 1) if path in exp), None)
    rows.append({
        "id": qid,
        "query": queries[qid]["query"],
        "category": queries[qid].get("category"),
        "expected_sources": exp,
        "observed_route": None,
        "lexical_top10": None,
        "text_vector_top10": None,
        "code_vector_top10": None,
        "rrf_top10": None,
        "final_top10": tops,
        "first_expected_rank": rank,
        "hit_at_5": rank is not None and rank <= 5,
        "hit_at_10": rank is not None,
        "failure_reason": "UNDETERMINED_NEEDS_CANDIDATE_TRACE" if rank is None or rank > 5 else None,
        "evidence_gaps": ["route_per_query", "lexical_candidates", "text_vector_candidates", "code_vector_candidates", "rrf_candidates"],
    })
stats = {
    "query_count": len(rows),
    "hit_at_5": sum(r["hit_at_5"] for r in rows),
    "hit_at_10": sum(r["hit_at_10"] for r in rows),
    "miss_at_5": sum(not r["hit_at_5"] for r in rows),
    "miss_at_10": sum(not r["hit_at_10"] for r in rows),
    "mrr": sum(1.0/r["first_expected_rank"] for r in rows if r["first_expected_rank"])/len(rows),
    "by_category": {k: {"count":sum(r["category"]==k for r in rows),"miss_at_10":sum(r["category"]==k and not r["hit_at_10"] for r in rows)} for k in sorted(set(r["category"] for r in rows))},
    "source": "saved RAG-014 benchmark; no new model inference",
    "limit": "Component-level candidate lists unavailable; no causal attribution possible yet",
}
assert abs(stats["hit_at_5"]/100-semantic["metrics"]["recall_at_5"])<1e-12
assert abs(stats["hit_at_10"]/100-semantic["metrics"]["recall_at_10"])<1e-12
assert abs(stats["mrr"]-semantic["metrics"]["mrr"])<1e-12
out = {"stage":"RAG-017-A","status":"PARTIAL_DIAGNOSTIC","stats":stats,"queries":rows}
dest = BENCH / "rag017_failure_matrix_initial.json"
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
print(json.dumps({"path":str(dest),"stats":stats},ensure_ascii=False,indent=2))
