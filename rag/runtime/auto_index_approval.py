"""RAG-AUTO-01.3: reviewed file-set manifest and explicit durable draft approval.

This module cannot start workers or publish indexes. Approval is only an
authorization record for a future supervisor which MUST reverify every source.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import json
import math
from pathlib import Path, PurePosixPath
import re
import time
from typing import Any, Iterable

from rag.runtime.auto_index_queue import (
    _connect, _canonical_queue_path, _PROJECT, _COLUMNS, _to_job,
    AutoIndexQueueError, get_job,
)
from rag.runtime.index_request import RagIndexScope, plan_rag_index

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_SOURCES = 2000
_MAX_MANIFEST_BYTES = 3 * 1024 * 1024


def _source_hash(root: Path, relative: str) -> str:
    posix = PurePosixPath(relative)
    if (not relative or posix.is_absolute() or ".." in posix.parts
            or posix.as_posix() != relative or "\\" in relative):
        raise ValueError("invalid path in approval manifest")
    source = (root / relative).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file() or source.is_symlink():
        raise ValueError("source escaped approval root")
    before = source.stat()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("source changed during hashing")
    return digest


def _canonical_preview(preview: dict) -> bytes:
    raw = {
        "schema_version": 1,
        "project_id": preview["project_id"],
        "source_root": preview["source_root"],
        "scope": preview["scope"],
        "sources": preview["sources"],
    }
    return json.dumps(
        raw,sort_keys=True,separators=(",",":"),ensure_ascii=False,
    ).encode("utf-8")


def build_auto_index_preview(
    project_id: str, source_root: str | Path, *, scope: str = "BOTH",
    paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Read-only planning using the canonical source-denial/secret scanner."""
    if not isinstance(project_id,str) or not _PROJECT.fullmatch(project_id):
        raise ValueError("invalid project namespace")
    try:
        selected_scope=RagIndexScope(scope)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid index scope") from exc
    root=Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source root is not a directory")
    plan=plan_rag_index(project_id,root,scope=selected_scope,paths=paths)
    if plan.candidate_count==0 or plan.candidate_count>_MAX_SOURCES:
        raise ValueError("preview has no approved candidates or too many files")
    sources=[]
    for item in sorted(plan.candidates,key=lambda p:p.path):
        sources.append({
            "path":item.path,
            "sha256":_source_hash(root,item.path),
            "index_kind":"CODE" if item.code_eligible else "TEXT",
        })
    preview={
        "schema_version":1,"project_id":project_id,
        "source_root":str(root),"scope":scope,
        "sources":sources,
    }
    packed=_canonical_preview(preview)
    if len(packed)>_MAX_MANIFEST_BYTES:
        raise ValueError("preview manifest exceeds configured size")
    return {
        **preview,
        "review_sha256":hashlib.sha256(packed).hexdigest(),
        "candidate_count":len(sources),
        "code_count":sum(x["index_kind"]=="CODE" for x in sources),
        "text_count":sum(x["index_kind"]=="TEXT" for x in sources),
        "denied_count":plan.denied_count,
        "unsupported_count":plan.unsupported_count,
        "sensitive_count":plan.sensitive_count,
        "queued":False,"approved":False,"worker_started":False,
        "publication_authorized":False,
    }


def revalidate_auto_index_preview(preview: dict) -> dict:
    """Fail closed if any source, policy decision, or preview field changes."""
    if not isinstance(preview,dict) or preview.get("schema_version")!=1:
        raise ValueError("invalid preview")
    supplied=preview.get("review_sha256")
    if not isinstance(supplied,str) or not _DIGEST.fullmatch(supplied):
        raise ValueError("invalid review digest")
    listed=preview.get("sources")
    if (not isinstance(listed,list) or not listed or len(listed)>_MAX_SOURCES
            or any(not isinstance(p,dict) for p in listed)):
        raise ValueError("invalid reviewed file set")
    paths=[item.get("path") for item in listed]
    if any(not isinstance(p,str) for p in paths) or len(set(paths))!=len(paths):
        raise ValueError("duplicate or malformed reviewed paths")
    current=build_auto_index_preview(
        preview["project_id"],preview["source_root"],
        scope=preview["scope"],paths=paths,
    )
    if not hmac.compare_digest(current["review_sha256"],supplied):
        raise ValueError("source, scope or eligibility changed; refresh approval")
    if current["sources"]!=listed:
        raise ValueError("approved sources no longer match")
    return current


def approve_auto_index_draft(
    queue_path: Path, job_id: str, preview: dict, *,
    confirmed_digest: str, operator_approved: bool=False,
    allow_write: bool=False, now_epoch: float | None=None,
) -> dict:
    """Persist exact reviewed snapshot; NEVER trigger models or publication."""
    if allow_write is not True or operator_approved is not True:
        raise PermissionError("explicit operator consent and write enable required")
    if not isinstance(confirmed_digest,str) or not _DIGEST.fullmatch(confirmed_digest):
        raise ValueError("confirmation must contain the full reviewed SHA-256")
    inspected=revalidate_auto_index_preview(preview)
    if not hmac.compare_digest(confirmed_digest,inspected["review_sha256"]):
        raise ValueError("confirmed fingerprint differs from live preview")
    now=time.time() if now_epoch is None else now_epoch
    if type(now) not in (int,float) or not math.isfinite(now) or now<0:
        raise ValueError("invalid event timestamp")
    row=get_job(queue_path,job_id)
    if row is None:
        raise AutoIndexQueueError("draft not found")
    if (row["project_id"]!=inspected["project_id"]
            or row["source_root"]!=inspected["source_root"]
            or row["requested_scope"]!=inspected["scope"]):
        raise AutoIndexQueueError("draft and reviewed project do not match")
    if row["state"]!="DRAFT" or row["approved"]:
        raise AutoIndexQueueError("only an unapproved draft may be authorized")
    # Snapshot hash list also remains in the durable audit trail. A later
    # worker must compare these SHA values against the actual source bytes.
    details={
        "review_sha256":inspected["review_sha256"],
        "source_root":inspected["source_root"],
        "scope":inspected["scope"],
        "sources":inspected["sources"],
    }
    encoded=json.dumps(details,sort_keys=True,separators=(",",":"))
    if len(encoded.encode("utf-8"))>_MAX_MANIFEST_BYTES:
        raise ValueError("review receipt too large")
    path=_canonical_queue_path(queue_path)
    with closing(_connect(path,create=True)) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            check=cn.execute(
                "SELECT state,approved,project_id,source_root,requested_scope "
                "FROM auto_jobs WHERE job_id=?",(job_id,),
            ).fetchone()
            if check!=("DRAFT",0,inspected["project_id"],
                        inspected["source_root"],inspected["scope"]):
                raise AutoIndexQueueError("draft changed before authorization")
            # Race defense: ensure the snapshot is still valid at the moment
            # of committing the approval while transaction is held.
            revalidate_auto_index_preview(preview)
            updated=cn.execute(
                "UPDATE auto_jobs SET approved=1,state='QUEUED',"
                "file_count=?,updated_at_epoch=? WHERE job_id=? "
                "AND state='DRAFT' AND approved=0",
                (inspected["candidate_count"],now,job_id),
            )
            if updated.rowcount!=1:
                raise AutoIndexQueueError("approval lost race")
            cn.execute(
                "INSERT INTO auto_job_events(job_id,event_type,"
                "recorded_at_epoch,details_json) VALUES(?,?,?,?)",
                (job_id,"SOURCE_REVIEW_CONFIRMED",now,encoded),
            )
            cn.execute("COMMIT")
        except BaseException:
            cn.execute("ROLLBACK")
            raise
    return {
        "job_id":job_id,"state":"QUEUED",
        "review_sha256":inspected["review_sha256"],
        "files_confirmed":inspected["candidate_count"],
        "source_review_confirmed":True,"worker_started":False,
        "job_enqueued":True,"publication_authorized":False,
    }


def read_reviewed_sources(queue_path: Path, job_id: str) -> dict:
    """Read a durable snapshot to enable independent pre-run validation."""
    job=get_job(queue_path,job_id)
    if job is None or not job["approved"]:
        raise PermissionError("job not approved")
    with closing(_connect(_canonical_queue_path(queue_path),create=False)) as cn:
        row=cn.execute(
            "SELECT details_json FROM auto_job_events "
            "WHERE job_id=? AND event_type='SOURCE_REVIEW_CONFIRMED' "
            "ORDER BY event_id DESC LIMIT 1",(job_id,),
        ).fetchone()
    if row is None:
        raise AutoIndexQueueError("approved job has no durable source receipt")
    receipt=json.loads(row[0])
    if receipt["source_root"]!=job["source_root"] or receipt["scope"]!=job["requested_scope"]:
        raise AutoIndexQueueError("review receipt does not match job")
    return receipt
