"""RAG-DEL-01.04-A: transactional catalog replacement lab.

Strictly TEST-ONLY: rejects catalogs outside the OS temporary directory.
This is not an operational activation API for real knowledge.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import uuid

from rag.runtime.auto_index_canary import (
    _atomic_write, _catalog_bytes, _catalog_mutex, _parse_catalog, _read_pointer,
)
from rag.runtime.knowledge_deletion_catalog_plan import (
    plan_private_generation_replacement,
)

class DeletionSwapError(RuntimeError):
    pass

def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()

def _journal_payload(record: dict) -> bytes:
    unsigned={key:value for key,value in record.items() if key!="journal_sha256"}
    canonical=json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    record["journal_sha256"]=_sha(canonical)
    return (json.dumps(record,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")


def _validate_journal(record: dict):
    if not isinstance(record,dict) or not isinstance(record.get("journal_sha256"),str):
        raise DeletionSwapError("journal signature missing")
    digest=record["journal_sha256"]
    unsigned={key:value for key,value in record.items() if key!="journal_sha256"}
    canonical=json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    if digest!=_sha(canonical):
        raise DeletionSwapError("journal record changed")


def _lab_paths(catalog_file: Path, pointer: Path):
    input_catalog=Path(catalog_file)
    input_pointer=Path(pointer)
    for supplied in (input_catalog, input_pointer):
        if not supplied.is_absolute():
            raise DeletionSwapError("laboratory paths must be absolute")
        # Prevent a redirected parent escaping the authorized scratch root.
        for part in (supplied, *supplied.parents):
            if part.exists() and (part.is_symlink() or (
                hasattr(part,"is_junction") and part.is_junction()
            )):
                raise DeletionSwapError("redirected laboratory path forbidden")
    catalog=input_catalog.resolve()
    public=input_pointer.resolve()
    temp=Path(tempfile.gettempdir()).resolve()
    # Only an ephemeral unittest-style scratch directory is accepted.
    lab_name=catalog.parent.name
    if (not (lab_name.startswith("tmp") and lab_name != "tmp")
            or not catalog.is_relative_to(temp) or catalog.parent==temp
            or not public.is_relative_to(temp) or public.parent==temp
            or catalog.parent!=public.parent
            or catalog.name!="project-indexes.json"):
        raise DeletionSwapError("temporary, same-directory laboratory only")
    if (catalog.is_symlink() or public.is_symlink()
            or (hasattr(catalog, "is_junction") and catalog.is_junction())
            or (hasattr(public, "is_junction") and public.is_junction())):
        raise DeletionSwapError("redirected lab path forbidden")
    return catalog,public

def laboratory_swap(project_id: str, expected_revision: str, candidate: dict, *,
                    catalog_file: Path, public_pointer: Path,
                    operator_approved: bool=False, laboratory_mode: bool=False,
                    _fail_at: str|None=None) -> dict:
    if operator_approved is not True or laboratory_mode is not True:
        raise PermissionError("explicit laboratory approval required")
    catalog,pointer=_lab_paths(catalog_file,public_pointer)
    with _catalog_mutex(catalog.parent):
        # No new transition while any earlier journal is unresolved.
        for pending in catalog.parent.glob("rag-del-*.journal.json"):
            if (not pending.is_file() or pending.is_symlink()
                    or (hasattr(pending, "is_junction") and pending.is_junction())):
                raise DeletionSwapError("redirected transaction journal")
            tid=pending.name[len("rag-del-"):-len(".journal.json")]
            if len(tid)!=32 or any(c not in "0123456789abcdef" for c in tid):
                raise DeletionSwapError("invalid prior transaction name")
            prior=json.loads(pending.read_text(encoding="utf-8"))
            _validate_journal(prior)
            backup=catalog.parent/("rag-del-"+tid+".previous.json")
            if (prior.get("schema_version")!=1
                    or prior.get("transaction")!=tid
                    or prior.get("catalog")!=str(catalog)
                    or prior.get("backup")!=str(backup)
                    or prior.get("state") not in ("PREPARED", "ACTIVE", "ROLLED_BACK")
                    or not backup.is_file() or backup.is_symlink()
                    or (hasattr(backup, "is_junction") and backup.is_junction())
                    or _sha(backup.read_bytes())!=prior.get("old_sha256")):
                raise DeletionSwapError("invalid prior transaction or backup")
            if prior["state"]!="ROLLED_BACK":
                raise DeletionSwapError("unresolved prior transaction; reconcile first")
        plan=plan_private_generation_replacement(catalog,pointer,project_id,expected_revision,candidate)
        before=_catalog_bytes(catalog)
        before_pointer=_read_pointer(pointer)
        if plan["old_catalog_sha256"]!=_sha(before) or plan["public_pointer_sha256"]!=_sha(before_pointer):
            raise DeletionSwapError("preflight drift")
        updated=_parse_catalog(before)
        updated["projects"][project_id]=candidate
        target=(json.dumps(updated,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode()
        if _sha(target)!=plan["proposed_catalog_sha256"]:
            raise DeletionSwapError("candidate projection mismatch")
        transaction=uuid.uuid4().hex
        backup=catalog.parent/("rag-del-"+transaction+".previous.json")
        journal=catalog.parent/("rag-del-"+transaction+".journal.json")
        _atomic_write(backup,before)
        record={"schema_version":1,"state":"PREPARED","transaction":transaction,
                "project_id":project_id,"catalog":str(catalog),"backup":str(backup),
                "old_sha256":_sha(before),"new_sha256":_sha(target),
                "public_pointer_sha256":_sha(before_pointer)}
        _atomic_write(journal,_journal_payload(record))
        if _fail_at=="before":
            raise DeletionSwapError("injected pre-switch failure")
        if _catalog_bytes(catalog)!=before or _read_pointer(pointer)!=before_pointer:
            raise DeletionSwapError("concurrent modification detected")
        _atomic_write(catalog,target)
        if _fail_at=="after":
            raise DeletionSwapError("injected post-switch failure")
        if _catalog_bytes(catalog)!=target or _read_pointer(pointer)!=before_pointer:
            raise DeletionSwapError("post-switch mismatch; rollback required")
        record["state"]="ACTIVE"
        _atomic_write(journal,_journal_payload(record))
        return {"state":"LAB_SWAP_ACTIVE","transaction":transaction,
                "journal":str(journal),"public_pointer_updated":False,
                "operational_use_allowed":False}

def laboratory_rollback(transaction: str, *,catalog_file: Path,public_pointer: Path,
                        operator_approved: bool=False,laboratory_mode: bool=False) -> dict:
    if operator_approved is not True or laboratory_mode is not True:
        raise PermissionError("explicit laboratory rollback approval required")
    if len(transaction)!=32 or any(ch not in "0123456789abcdef" for ch in transaction):
        raise DeletionSwapError("invalid transaction")
    catalog,pointer=_lab_paths(catalog_file,public_pointer)
    journal=catalog.parent/("rag-del-"+transaction+".journal.json")
    expected_backup=catalog.parent/("rag-del-"+transaction+".previous.json")
    with _catalog_mutex(catalog.parent):
        if not journal.is_file() or journal.is_symlink() or not expected_backup.is_file() or expected_backup.is_symlink():
            raise DeletionSwapError("missing transaction journal or backup")
        data=json.loads(journal.read_text(encoding="utf-8"))
        _validate_journal(data)
        if (data.get("schema_version")!=1 or data.get("transaction")!=transaction
                or data.get("catalog")!=str(catalog) or data.get("backup")!=str(expected_backup)
                or data.get("state") not in ("PREPARED","ACTIVE","ROLLED_BACK")):
            raise DeletionSwapError("journal mismatch")
        old=expected_backup.read_bytes()
        if _sha(old)!=data.get("old_sha256") or _sha(_read_pointer(pointer))!=data.get("public_pointer_sha256"):
            raise DeletionSwapError("backup or public pointer changed")
        present=_catalog_bytes(catalog)
        if _sha(present)==data["old_sha256"]:
            state="ALREADY_ROLLED_BACK"
        elif _sha(present)==data.get("new_sha256"):
            _atomic_write(catalog,old)
            if _catalog_bytes(catalog)!=old:
                raise DeletionSwapError("rollback verification failure")
            state="LAB_ROLLBACK_COMPLETE"
        else:
            raise DeletionSwapError("catalog modified by another transaction")
        data["state"]="ROLLED_BACK"
        _atomic_write(journal,_journal_payload(data))
        return {"state":state,"public_pointer_updated":False,"operational_use_allowed":False}
