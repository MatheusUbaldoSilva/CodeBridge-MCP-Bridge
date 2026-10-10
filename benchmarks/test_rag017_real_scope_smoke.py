"""Real persistent-index scope smoke, opt-in Code-only; no app activation."""
import json,time
from pathlib import Path
from unittest.mock import patch
from rag.contracts import SearchQuery,SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.production_search import search_persistent_semantic
from rag.runtime.resident_models import resident_pool
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local

cases=[
 ("project_only",dict(project_id="codebridge")),
 ("branch_nonexistent",dict(project_id="codebridge",branch="__rag017_no_such_branch__")),
 ("path_nonexistent",dict(project_id="codebridge",path_filter="__rag017_no_such_path__")),
 ("source_code",dict(project_id="codebridge",source_types=(SourceType.CODE,))),
 ("combined_existing_filter",dict(project_id="codebridge",source_types=(SourceType.CODE,),path_filter="rag/")),
 ("combined_nonexistent_branch",dict(project_id="codebridge",source_types=(SourceType.CODE,),path_filter="rag/",branch="__rag017_no_such_branch__")),
 ("other_project",dict(project_id="rag017-no-such-project")),
]
client=open_qdrant_local()
records=[]
try:
 with patch.dict(search_persistent_semantic.__globals__,{"open_qdrant_local":lambda *a,**kw:client,"close_qdrant_local":lambda c:None}):
  for name,settings in cases:
   query=SearchQuery(query="Locate code embedding and indexing implementation",top_k=10,**settings)
   start=time.perf_counter()
   found=search_persistent_semantic(query,QueryRoute.CODE,experimental_cross_route=True,experimental_resident_models=True)
   correct=all(item.metadata.project_id==query.project_id and (query.branch is None or item.metadata.git_branch==query.branch) and (not query.source_types or item.metadata.source_type in query.source_types) and (query.path_filter is None or query.path_filter in (item.metadata.path or "").replace("\\","/")) for item in found)
   record={"case":name,"results":len(found),"scoped":correct,"ms":round((time.perf_counter()-start)*1000,2)}
   records.append(record)
   print("CASE",json.dumps(record),flush=True)
finally:
 resident_pool.close()
 close_qdrant_local(client)
passed=all(item["scoped"] for item in records) and all(item["results"]==0 for item in records if item["case"] in ("branch_nonexistent","path_nonexistent","combined_nonexistent_branch","other_project"))
report={"cases":records,"passed":passed,"gate":"BLOCKED","note":"Real persistent index with opt-in Code-only, no production wiring."}
Path(__file__).with_name("rag017_real_scope_smoke.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
print("SUMMARY",json.dumps({"passed":passed,"count":len(records)}),flush=True)
if not passed:raise SystemExit(1)
