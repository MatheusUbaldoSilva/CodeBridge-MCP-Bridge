"""Finalize RAG-017-A evidence matrix after real semantic replay."""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

root=Path(__file__).resolve().parents[1]
bench=root/"benchmarks"
def load(name):
    return json.loads((bench/name).read_text(encoding="utf-8"))
def jsonl(name):
    return [json.loads(x) for x in (bench/name).read_text(encoding="utf-8").splitlines() if x.strip()]
dataset=jsonl("rag014_dataset.jsonl")
truth=jsonl("rag014_ground_truth.jsonl")
replay=load("rag017_replay_latest.json")
trace=load("rag017_component_trace.json")
expected={r["id"]:set(r["expected_paths"]) for r in truth}
assert len(dataset)==len(expected)==len(trace)==100
rows=[]
for q in dataset:
    k=q["id"]
    c=trace[k]
    exp=expected[k]
    rrf=c["rrf_top10"]
    final=c["final_top10"]
    first=next((i for i,p in enumerate(final,1) if p in exp),None)
    lex=any(p in exp for p in c["lexical_top10"])
    txt=any(p in exp for p in c["text_vector_top10"])
    cod=any(p in exp for p in c["code_vector_top10"])
    fused=any(p in exp for p in rrf)
    if first is None:
        if not (lex or txt or cod):
            reason="RETRIEVAL_CANDIDATE_MISS"
        elif not fused:
            reason="RRF_RANKING_OR_CUTOFF"
        else:
            reason="DEDUP_OR_TOP_K_CUTOFF"
    elif first>5:
        reason="TOP_K_5_CUTOFF"
    else:
        reason=None
    rows.append({"id":k,"query":q["query"],"category":q.get("category"),"route":c["route"],"expected_sources":sorted(exp),"lexical_top10":c["lexical_top10"],"text_vector_top10":c["text_vector_top10"],"code_vector_top10":c["code_vector_top10"],"rrf_top10":rrf,"final_top10":final,"first_expected_rank":first,"failure_reason":reason,"candidate_hits":{"lexical":lex,"text_vector":txt,"code_vector":cod,"rrf":fused},"notes":"Candidate lists limited to top10; categorization is observational, not proven root cause."})
metrics={"query_count":100,"hit_at_5":sum((r["first_expected_rank"] or 99)<=5 for r in rows),"hit_at_10":sum(r["first_expected_rank"] is not None for r in rows),"mrr":sum(1/r["first_expected_rank"] for r in rows if r["first_expected_rank"])/100}
assert abs(metrics["hit_at_5"]/100-replay["metrics"]["recall_at_5"])<1e-12
assert abs(metrics["hit_at_10"]/100-replay["metrics"]["recall_at_10"])<1e-12
assert abs(metrics["mrr"]-replay["metrics"]["mrr"])<1e-12
counts=dict(Counter(r["failure_reason"] or "HIT_TOP5" for r in rows))
report={"stage":"RAG-017-A","status":"DIAGNOSTIC_COMPLETE","metrics":metrics,"failure_categories":counts,"limits":["Candidate top10 only","No causal attribution without controlled changes","Replay metrics may diverge from frozen report if repository changed"],"queries":rows}
(bench/"rag017_failure_matrix.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
text=["# RAG-017-A â€” Diagnostico das 100 queries","","Diagnostico de observacao, sem alteracao dos algoritmos nem dos thresholds.","","## Medidas",f"- Acertos top 5: {metrics['hit_at_5']}/100",f"- Acertos top 10: {metrics['hit_at_10']}/100",f"- MRR: {metrics['mrr']:.6f}","","## Categorias observadas"]
text.extend(f"- {a}: {b}" for a,b in sorted(counts.items()))
text+=["","## Limites","Classificacoes indicam em qual etapa a fonte esperada desapareceu das listas inspecionadas; nao comprovam a causa-raiz.","","## Proximos passos","RAG-017-B lexical/normalizacao; RAG-017-C classificacao de rota; RAG-017-D chunking/embeddings; RAG-017-E RRF e dedup.","","## Evidencia","benchmarks/rag017_failure_matrix.json (100 queries completas), benchmarks/rag017_component_trace.json, benchmarks/rag017_replay_latest.json."]
(root/"docs"/"RAG_017_A_DIAGNOSTICO.md").write_text("\n".join(text)+"\n",encoding="utf-8")
print(json.dumps({"metrics":metrics,"counts":counts,"rows":len(rows)},indent=2))
