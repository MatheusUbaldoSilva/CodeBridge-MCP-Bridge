"""RAG-017-E offline evaluation of source diversity after RRF."""
from pathlib import Path
from collections import Counter
import json
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/"benchmarks"
base=json.loads((B/"rag017_failure_matrix.json").read_text(encoding="utf-8"))
rows=[]
for r in base["queries"]:
    expected=set(r["expected_sources"])
    rrf=r["rrf_top10"]
    final=r["final_top10"]
    seen=set()
    diversified=[]
    for path in rrf:
        if path not in seen:
            seen.add(path)
            diversified.append(path)
    def hit(paths,k):
        return any(p in expected for p in paths[:k])
    rows.append({"id":r["id"],"expected":sorted(expected),"rrf_top10":rrf,"final_top10":final,"unique_paths_in_rrf_top10":len(set(rrf)),"duplicated_path_slots":len(rrf)-len(set(rrf)),"baseline_hit5":hit(final,5),"baseline_hit10":hit(final,10),"rrf_hit5":hit(rrf,5),"rrf_hit10":hit(rrf,10),"diversified_hit5":hit(diversified,5),"diversified_hit10":hit(diversified,10),"dedup_dropped_expected":hit(rrf,10) and not hit(final,10)})
stats={"queries":len(rows),"rrf_hit5":sum(r["rrf_hit5"] for r in rows),"rrf_hit10":sum(r["rrf_hit10"] for r in rows),"final_hit5":sum(r["baseline_hit5"] for r in rows),"final_hit10":sum(r["baseline_hit10"] for r in rows),"offline_unique_path_hit5":sum(r["diversified_hit5"] for r in rows),"offline_unique_path_hit10":sum(r["diversified_hit10"] for r in rows),"mean_duplicate_path_slots":sum(r["duplicated_path_slots"] for r in rows)/len(rows),"dedup_dropped_expected":sum(r["dedup_dropped_expected"] for r in rows)}
out={"stage":"RAG-017-E","evaluation":"offline diagnostic on RRF top10 paths only; candidate list truncation prevents conclusions about full pipeline quality","statistics":stats,"queries":rows}
(B/"rag017e_fusion_ablation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(stats,indent=2))
