"""End-to-end local opt-in cross-route timing; production remains disabled."""
from __future__ import annotations
import json,time
from pathlib import Path
from rag.contracts import SearchQuery
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.status import build_rag_status
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from benchmarks.run_rag014_semantic_benchmark import process_rss_bytes
import os
rows=[]
queries=["How is a Git provenance commit associated with a document?", "What happens if get_context refers to a missing chunk?"]
for query in queries:
 started=time.perf_counter()
 result=search_persistent_semantic(SearchQuery(query=query,project_id="codebridge",top_k=10), QueryRoute.TEXT,experimental_cross_route=True)
 elapsed=(time.perf_counter()-started)*1000
 rows.append({"query":query,"elapsed_ms":elapsed,"results":[x.metadata.path for x in result],"rss_bytes":process_rss_bytes(os.getpid())})
 print("QUERY_TIMED",round(elapsed,2),flush=True)
report={"mode":"opt-in-real-end-to-end-text+code","sample_count":len(rows),"measurements":rows,"gate":"BLOCKED","warning":"two smoke queries not official cold/warm p95 and no independent quality holdout"}
p=Path(__file__).resolve().parent/"rag017_cross_route_runtime_smoke.json"
p.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2),flush=True)
