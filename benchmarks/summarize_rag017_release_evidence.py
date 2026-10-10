"""Read-only release gate evidence from versioned RAG-017 artifacts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text(encoding="utf8"))
quality=read("rag017_code_only_ablation.json")
load=read("rag017_code_only_load_60.json")
memory=read("rag017_code_only_aggregate_rss.json")
gpu=read("rag017_code_only_resource_peak.json")
recovery=read("rag017_concurrent_recovery.json")
report={
 "release_approved":False,
 "blockers":["independent externally reviewed holdout not provided","end-to-end installed service validation incomplete","representative production workload and end-to-end resource peak not certified"],
 "evidence":{
  "known_dataset_quality":quality,
  "load":{"warm_count":load.get("warm_count"),"p95_ms":load.get("warm_p95_ms"),"cold_ms":load.get("cold_ms")},
  "memory":{"peak_parent_plus_model_rss_mib":memory.get("peak_combined_parent_plus_model_rss_mib"),"sample_count":memory.get("sample_count")},
  "gpu":{"peak_device_used_mib":gpu.get("peak_gpu_used_mib"),"sample_count":gpu.get("samples")},
  "recovery":{"first_concurrent_request_failed":not recovery["simultaneous"][0]["ok"],"later_request_ok":recovery["subsequent_ok"]}
 },
 "notes":"Known dataset used for tuning; not independent holdout. Peaks are sampled, not guaranteed instantaneous maxima."
}
target=ROOT/"rag017_release_evidence_summary.json"
target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
print(json.dumps({"approved":report["release_approved"],"blockers":report["blockers"],"output":str(target)}))
