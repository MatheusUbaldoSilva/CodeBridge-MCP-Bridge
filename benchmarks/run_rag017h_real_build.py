"""RAG-017-H explicit first production index for authorized CodeBridge sources."""
from pathlib import Path
from rag.runtime.index_request import plan_rag_index,RagIndexScope
from rag.runtime.production_index import build_staged_index
from rag.runtime.production_publish import publish_staged_index,validate_staged_index
from rag.runtime.status import build_rag_status

ROOT=Path(__file__).resolve().parents[1]
before=build_rag_status()
if any((before.index["manifest_exists"],before.index["sqlite_exists"],before.index["qdrant_exists"])):
    raise RuntimeError("Refusing first publish: production data already exists")
plan=plan_rag_index("codebridge",ROOT,scope=RagIndexScope.BOTH,paths=("rag","author_mcp","docs"))
print(f"BUILD_START candidates={plan.candidate_count} denied={plan.denied_count} unsupported={plan.unsupported_count}",flush=True)
if plan.candidate_count<50:
    raise RuntimeError("Unexpectedly small authorized scope")
stage=build_staged_index(plan)
print("STAGING_DONE",stage,flush=True)
quality=validate_staged_index(stage["staging_path"],"codebridge")
print("STAGING_VALIDATED",quality,flush=True)
published=publish_staged_index(stage["staging_path"],"codebridge",ROOT)
print("PUBLISHED",published,flush=True)
after=build_rag_status()
assert after.index["state"]=="READY",after.index
print("PERSISTENT_READY",after.index,flush=True)
