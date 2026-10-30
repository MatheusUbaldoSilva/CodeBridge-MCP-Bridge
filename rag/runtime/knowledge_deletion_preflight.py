"""RAG-DEL private catalog preflight. Read-only, NEVER authorizes activation."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from rag.runtime.auto_index_canary import _read_pointer,_parse_catalog
from rag.runtime.knowledge_deletion_catalog_plan import plan_private_generation_replacement

class PrivateDeletionPreflightError(RuntimeError):
    pass

def inspect_private_deletion_preflight(catalog_file:Path,public_pointer:Path,
                                       project_id:str,expected_revision:str,
                                       candidate:dict)->dict:
    catalog=Path(catalog_file)
    pointer=Path(public_pointer)
    if (not catalog.is_absolute() or not pointer.is_absolute()
            or not catalog.is_file() or catalog.is_symlink()
            or not pointer.is_file() or pointer.is_symlink()
            or catalog.name!="project-indexes.json"
            or project_id=="codebridge"):
        raise PrivateDeletionPreflightError("unsafe catalog or public pointer")
    for path in (catalog,pointer):
        for parent in (path,*path.parents):
            if parent.exists() and (parent.is_symlink() or (
                hasattr(parent,"is_junction") and parent.is_junction()
            )):
                raise PrivateDeletionPreflightError("redirected catalog path")
    if candidate.get("index_family")!="RAG_DEL_01" or candidate.get("project_id")!=project_id:
        raise PrivateDeletionPreflightError("candidate is not a private deletion generation")
    # Verify the catalog has no incomplete deletion journal; never repair it here.
    pending=[]
    for file in catalog.parent.glob("rag-del-*.journal.json"):
        if not file.is_file() or file.is_symlink():
            raise PrivateDeletionPreflightError("invalid journal entry")
        from rag.runtime.knowledge_deletion_swap_lab import _validate_journal
        record=json.loads(file.read_text(encoding="utf-8"))
        _validate_journal(record)
        if record.get("state")!="ROLLED_BACK":
            pending.append(file.name)
    if pending:
        raise PrivateDeletionPreflightError("unresolved deletion transactions: "+str(len(pending)))
    plan=plan_private_generation_replacement(
        catalog,pointer,project_id,expected_revision,candidate)
    # Re-open snapshots and reject read drift between calls.
    raw=catalog.read_bytes()
    public=_read_pointer(pointer)
    if sha256(raw).hexdigest()!=plan["old_catalog_sha256"]:
        raise PrivateDeletionPreflightError("catalog changed during inspection")
    if sha256(public).hexdigest()!=plan["public_pointer_sha256"]:
        raise PrivateDeletionPreflightError("public pointer changed during inspection")
    return {
        "state":"PRIVATE_DELETION_PREFLIGHT_READ_ONLY",
        "project_id":project_id,"expected_revision":expected_revision,
        "old_catalog_sha256":plan["old_catalog_sha256"],
        "public_pointer_sha256":plan["public_pointer_sha256"],
        "pending_deletion_transactions":0,
        "candidate_verified":False,
        "catalog_modified":False,"activation_authorized":False,
    }
