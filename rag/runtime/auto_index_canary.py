"""RAG-AUTO-03.4/03.5: journaled READ-ONLY canary catalog registration.

NEVER writes the public active-generation.json or overwrites an existing
project record. Uses exact prior-catalog backup and compare-before-replace
rollback. Tests can inject an isolated catalog and fake public pointer.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from rag.runtime.auto_index_generation import verify_prepared_auto_generation
from rag.runtime.auto_index_queue import get_job

class AutoCanaryError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pointer(pointer: Path) -> bytes:
    raw=pointer.read_bytes()
    payload=json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(payload,dict)
            or payload.get("schema_version")!=1
            or not isinstance(payload.get("generation"),str)
            or not payload["generation"]):
        raise AutoCanaryError("public generation pointer invalid")
    return raw


def _atomic_write(path: Path,content: bytes) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",dir=path.parent,prefix=".auto-canary-",
            suffix=".tmp",delete=False,
        ) as stream:
            name=Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
        name=None
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


@contextmanager
def _catalog_mutex(directory: Path):
    """Serialize our canary operations across local Python processes."""
    import msvcrt
    directory.mkdir(parents=True,exist_ok=True)
    lock=directory/"auto-canary.lock"
    with lock.open("a+b") as file:
        file.seek(0,os.SEEK_END)
        if file.tell()==0:
            file.write(b"0")
            file.flush()
        file.seek(0)
        msvcrt.locking(file.fileno(),msvcrt.LK_LOCK,1)
        try:
            yield
        finally:
            file.seek(0)
            msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)


def _validate_catalog_path(catalog_file: Path,workspace: Path) -> tuple[Path,Path]:
    catalog=Path(catalog_file).absolute()
    root=Path(workspace).resolve(strict=True)
    if catalog.name!="project-indexes.json":
        raise AutoCanaryError("only project-indexes.json catalog is supported")
    if root.is_relative_to(catalog.parent.resolve()) or catalog.parent.resolve().is_relative_to(root):
        raise AutoCanaryError("catalog and workspace must be independent")
    if catalog.is_symlink() or (
        hasattr(catalog,"is_junction") and catalog.is_junction()
    ):
        raise AutoCanaryError("catalog redirection forbidden")
    return catalog,root


def _catalog_bytes(catalog: Path) -> bytes:
    if catalog.is_file():
        return catalog.read_bytes()
    return b'{"schema_version":1,"projects":{}}\n'


def _parse_catalog(raw: bytes) -> dict:
    data=json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(data,dict) or data.get("schema_version")!=1
            or not isinstance(data.get("projects"),dict)):
        raise AutoCanaryError("invalid catalog schema")
    return data


def _row(queue_path: Path,job_id: str,python_executable: Path,workspace: Path) -> dict:
    job=get_job(queue_path,job_id)
    if job is None or job["state"]!="READY_FOR_REVIEW":
        raise AutoCanaryError("job is not ready")
    verified=verify_prepared_auto_generation(queue_path,job_id)
    generation=Path(verified["generation"]).resolve(strict=True)
    source=Path(verified["source_snapshot"]).resolve(strict=True)
    if not generation.is_relative_to(workspace) or not source.is_relative_to(workspace):
        raise AutoCanaryError("candidate outside approved workspace")
    python=Path(python_executable).resolve(strict=True)
    if not python.is_file():
        raise AutoCanaryError("approved Python runtime missing")
    receipt=generation/"auto-generation-receipt.json"
    return {
        "index_family":"RAG_AUTO_03",
        "enabled":True,"project_id":job["project_id"],
        "job_id":job_id,
        "source_revision":verified["source_revision"],
        "generation_directory":str(generation),
        "source_directory":str(source),
        "python_executable":str(python),
        "sqlite_sha256":verified["sqlite_sha256"],
        "manifest_sha256":verified["manifest_sha256"],
        "generation_receipt_sha256":_sha(receipt.read_bytes()),
    }


def activate_auto_canary(
    queue_path: Path,job_id: str, *,
    catalog_file: Path,public_pointer: Path,workspace: Path,
    python_executable: Path,operator_approved: bool=False,
    confirmation: str|None=None,
    _test_fail_at: str|None=None,
) -> dict:
    job=get_job(queue_path,job_id)
    if job is None or job["project_id"]=="codebridge":
        raise AutoCanaryError("public CodeBridge namespace cannot be modified")
    if operator_approved is not True or confirmation!=(
        "RAG_AUTO_CANARY:"+job["project_id"]+":"+job_id
    ):
        raise PermissionError("explicit isolated-canary confirmation required")
    catalog,root=_validate_catalog_path(catalog_file,workspace)
    before_pointer=_read_pointer(public_pointer)
    candidate=_row(queue_path,job_id,python_executable,root)
    journal=catalog.parent/("auto-canary-"+job_id+".journal.json")
    backup=catalog.parent/("auto-canary-"+job_id+".previous.json")
    with _catalog_mutex(catalog.parent):
        old=_catalog_bytes(catalog)
        reused=False
        previous=None
        if journal.exists() or backup.exists():
            if not journal.is_file() or not backup.is_file():
                raise AutoCanaryError("incomplete prior transition")
            previous=json.loads(journal.read_text(encoding="utf-8"))
            if (previous.get("state")!="ROLLED_BACK"
                    or previous.get("job_id")!=job_id
                    or previous.get("project_id")!=job["project_id"]
                    or previous.get("catalog")!=str(catalog)
                    or previous.get("backup")!=str(backup)
                    or previous.get("old_sha256")!=_sha(old)
                    or _sha(backup.read_bytes())!=_sha(old)
                    or previous.get("public_pointer_sha256")!=_sha(before_pointer)):
                raise AutoCanaryError("previous transition not safely rolled back")
            reused=True
        existing=_parse_catalog(old)
        if job["project_id"] in existing["projects"]:
            raise AutoCanaryError("project already registered; replacement is prohibited")
        existing["projects"][job["project_id"]]=candidate
        updated=(json.dumps(existing,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
        if _read_pointer(public_pointer)!=before_pointer:
            raise AutoCanaryError("public pointer changed before canary commit")
        # Durable prior state and recovery journal before atomic switch.
        if not reused:
            _atomic_write(backup,old)
        intent={
            "schema_version":1,"state":"PREPARED",
            "activation_attempt":(int(previous.get("activation_attempt",1))+1
                                  if reused else 1),
            "project_id":job["project_id"],"job_id":job_id,
            "backup":str(backup),"catalog":str(catalog),
            "old_sha256":_sha(old),"new_sha256":_sha(updated),
            "public_pointer_sha256":_sha(before_pointer),
        }
        _atomic_write(journal,(json.dumps(intent,indent=2,sort_keys=True)+"\n").encode())
        if _catalog_bytes(catalog)!=old:
            raise AutoCanaryError("catalog changed before atomic replace")
        if _test_fail_at=="before":
            raise AutoCanaryError("injected failure before catalog replace")
        _atomic_write(catalog,updated)
        if _test_fail_at=="after":
            raise AutoCanaryError("injected failure after catalog replace")
        current=_parse_catalog(catalog.read_bytes())
        if (current["projects"].get(job["project_id"])!=candidate
                or _read_pointer(public_pointer)!=before_pointer):
            raise AutoCanaryError("canary verification failed; use journaled rollback")
        intent["state"]="CANARY_ACTIVE"
        _atomic_write(journal,(json.dumps(intent,indent=2,sort_keys=True)+"\n").encode())
    return {
        "state":"ISOLATED_CANARY_ACTIVE","project_id":job["project_id"],
        "job_id":job_id,"journal":str(journal),"backup":str(backup),
        "public_pointer_updated":False,"previous_catalog_preserved":True,
    }


def rollback_auto_canary(
    job_id: str, *,catalog_file: Path,public_pointer: Path,workspace: Path,
    operator_approved: bool=False,confirmation: str|None=None,
) -> dict:
    if operator_approved is not True or confirmation!="RAG_AUTO_CANARY_ROLLBACK:"+job_id:
        raise PermissionError("specific canary rollback confirmation required")
    if not re.fullmatch(r"[0-9a-f]{32}",job_id):
        raise ValueError("invalid job id")
    catalog,root=_validate_catalog_path(catalog_file,workspace)
    journal=catalog.parent/("auto-canary-"+job_id+".journal.json")
    with _catalog_mutex(catalog.parent):
        if not journal.is_file():
            raise AutoCanaryError("rollback journal missing")
        record=json.loads(journal.read_text(encoding="utf-8"))
        backup=Path(record.get("backup",""))
        expected_backup=catalog.parent/("auto-canary-"+job_id+".previous.json")
        if (record.get("job_id")!=job_id
                or record.get("schema_version")!=1
                or record.get("state") not in ("PREPARED","CANARY_ACTIVE","ROLLED_BACK")
                or backup!=expected_backup
                or record.get("catalog")!=str(catalog)):
            raise AutoCanaryError("rollback journal invalid")
        pointer=_read_pointer(public_pointer)
        if _sha(pointer)!=record.get("public_pointer_sha256"):
            raise AutoCanaryError("public generation changed since canary registration")
        old=backup.read_bytes()
        if _sha(old)!=record["old_sha256"]:
            raise AutoCanaryError("backup was modified")
        current=_catalog_bytes(catalog)
        if _sha(current)==record["old_sha256"]:
            result="ALREADY_ROLLED_BACK"
        elif _sha(current)!=record["new_sha256"]:
            raise AutoCanaryError("catalog changed after activation; manual reconciliation required")
        else:
            _atomic_write(catalog,old)
            if catalog.read_bytes()!=old:
                raise AutoCanaryError("rollback catalog verification failed")
            result="RESTORED_PREVIOUS_CATALOG"
        record["state"]="ROLLED_BACK"
        _atomic_write(journal,(json.dumps(record,indent=2,sort_keys=True)+"\n").encode())
    return {
        "state":result,"job_id":job_id,
        "public_pointer_updated":False,
        "generations_deleted":False,
        "backup_preserved":str(backup),
    }
