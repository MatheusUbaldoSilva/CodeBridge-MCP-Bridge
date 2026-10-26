"""RAG-AUTO-02.3–02.5: explicitly started, one-model-at-a-time worker.

One call processes at most 256 missing vectors. Safe checkpoints re-count Qdrant,
fence stale workers, and honor pause/cancel requests only between batches.
No scheduling or public RAG publication occurs in this module.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import threading
import time

from rag.runtime.auto_index_queue import (
    _canonical_queue_path,AutoIndexQueueError,get_job,
)
from rag.runtime.auto_index_approval import (
    read_reviewed_sources,revalidate_auto_index_preview,
)
from rag.runtime.auto_index_batch import select_auto_vector_batch
from rag.runtime.auto_index_checkpoint import update_auto_checkpoint,_require_owner
from rag.runtime.auto_index_staging import prepare_auto_staging
from rag.runtime.auto_index_supervisor import (
    reserve_index_supervisor,renew_index_supervisor,release_index_supervisor,
)


def _free_ram_mib() -> int:
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("psutil is required for safe RAM budget monitoring") from exc
    return int(psutil.virtual_memory().available // (1024*1024))


def _begin_batch(queue_path: Path,job_id: str,token: str,generation: int) -> None:
    path=_canonical_queue_path(queue_path)
    with closing(sqlite3.connect(path.as_uri()+"?mode=rw",uri=True,timeout=12,
                         isolation_level=None)) as cn:
        cn.execute("BEGIN IMMEDIATE")
        try:
            _require_owner(cn,job_id,token,generation,time.time())
            state=cn.execute(
                "SELECT state,approved FROM auto_jobs WHERE job_id=?",(job_id,),
            ).fetchone()
            if state!=("QUEUED",1):
                raise AutoIndexQueueError("job no longer QUEUED before batch")
            cn.execute("UPDATE auto_jobs SET state='RUNNING',updated_at_epoch=? "
                       "WHERE job_id=?",(time.time(),job_id))
            cn.execute("COMMIT")
        except BaseException:
            if cn.in_transaction:
                cn.execute("ROLLBACK")
            raise


def _real_embedding_writer(stage: Path,project_id: str,
                           text_rows: list,code_rows: list) -> None:
    from rag.runtime.production_index import _write_vectors
    _write_vectors(
        stage/"qdrant",project_id,text_rows,code_rows,
        text_cpu_only=bool(text_rows),
    )


def _revalidate_receipt(queue_path: Path,job_id: str) -> None:
    job=get_job(queue_path,job_id)
    receipt=read_reviewed_sources(queue_path,job_id)
    revalidate_auto_index_preview({
        "schema_version":1,"project_id":job["project_id"],
        "source_root":job["source_root"],"scope":job["requested_scope"],
        "sources":receipt["sources"],"review_sha256":receipt["review_sha256"],
    })


def _public_generation() -> str:
    import os
    base=os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("cannot verify production RAG pointer")
    pointer=Path(base)/"CodeBridge"/"rag"/"active-generation.json"
    value=json.loads(pointer.read_text(encoding="utf-8"))
    if value.get("schema_version")!=1 or not value.get("generation"):
        raise RuntimeError("public RAG pointer invalid")
    return value["generation"]


def execute_auto_vector_batch(
    queue_path: Path,job_id: str, *,operator_approved: bool=False,
    execute: bool=False,confirmation: str|None=None,
    max_vectors: int=256,prefer: str="TEXT",
    model_writer=None,memory_probe=None,semantic_guard_factory=None,
) -> dict:
    """One supervised batch; default settings execute real CODE GPU / TEXT CPU."""
    if execute is not True or operator_approved is not True or (
        confirmation!="RAG_AUTO_RUN:"+job_id
    ):
        raise PermissionError("explicit job-specific execution approval required")
    if type(max_vectors) is not int or not 1<=max_vectors<=256:
        raise ValueError("max_vectors must be 1..256")
    if prefer not in ("TEXT","CODE"):
        raise ValueError("invalid preferred embedding model")
    memory=_free_ram_mib if memory_probe is None else memory_probe
    if memory()<1600:
        return {"state":"WAITING_FOR_MEMORY","job_id":job_id,
                "minimum_free_mib":1600,"worker_started":False}
    original_generation=_public_generation()
    # The lock synchronizes with semantic inference in other CodeBridge
    # processes. Tests may inject a nullcontext but public API cannot.
    if semantic_guard_factory is None:
        from rag.runtime.production_generation_lock import production_generation_lock
        semantic_guard_factory=lambda:production_generation_lock(
            exclusive=True,channel="semantic",
        )
    reserve=reserve_index_supervisor(
        queue_path,job_id,reservation_enabled=True,operator_approved=True,
        lease_seconds=3600,
    )
    if reserve["state"]=="SUPERVISOR_BUSY":
        return {**reserve,"job_id":job_id}
    token=reserve["lease_token"]
    generation=reserve["generation"]
    event=threading.Event()
    lost=threading.Event()
    heartbeat=None
    started=False
    try:
        stage_info=prepare_auto_staging(
            queue_path,job_id,operator_approved=True,preparation_enabled=True,
        )
        selection=select_auto_vector_batch(
            queue_path,job_id,prefer=prefer,max_vectors=max_vectors,
        )
        initial=selection["inventory"]
        # A final crash after all points were upserted may leave an incomplete
        # status. Reconcile without launching another embedding model.
        _begin_batch(queue_path,job_id,token,generation)
        started=True
        def ping():
            while not event.wait(20):
                try:
                    renewed=renew_index_supervisor(
                        queue_path,job_id,token,generation,
                        lease_seconds=3600,
                    )
                    if not renewed["accepted"]:
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return
        heartbeat=threading.Thread(
            target=ping,name="rag-auto-lease-heartbeat",daemon=True,
        )
        heartbeat.start()
        rows=selection["rows"]
        if rows:
            if memory()<1600:
                raise RuntimeError("free RAM dropped below 1600 MiB")
            with semantic_guard_factory():
                _revalidate_receipt(queue_path,job_id)
                if _public_generation()!=original_generation:
                    raise RuntimeError("public generation changed during job")
                writer=_real_embedding_writer if model_writer is None else model_writer
                stage=Path(stage_info["stage"])
                writer(
                    stage,get_job(queue_path,job_id)["project_id"],
                    rows if selection["collection"]=="TEXT" else [],
                    rows if selection["collection"]=="CODE" else [],
                )
        if lost.is_set():
            raise AutoIndexQueueError("worker lost fencing heartbeat")
        from rag.runtime.auto_index_batch import inventory_auto_vectors
        current=inventory_auto_vectors(queue_path,job_id)
        if rows:
            ids=current["text_ids"] if selection["collection"]=="TEXT" else current["code_ids"]
            if not {row[0] for row in rows}.issubset(ids):
                raise AutoIndexQueueError("writer did not persist all selected vectors")
        if _public_generation()!=original_generation:
            raise RuntimeError("public generation changed during batch")
        validated=False
        if current["complete"]:
            _revalidate_receipt(queue_path,job_id)
            from rag.runtime.production_publish import validate_staged_index
            check=validate_staged_index(stage_info["stage"],initial["project_id"])
            if (check["chunks"]!=current["chunks"]
                    or check["text_vectors"]!=current["text_done"]
                    or check["code_vectors"]!=current["code_done"]):
                raise AutoIndexQueueError("staging validation disagreed with Qdrant")
            validated=True
        result=update_auto_checkpoint(
            queue_path,job_id,token,generation,validated=validated,
            last="PASS" if rows else "RECONCILED",
        )
        result.update({
            "batch_vectors_requested":len(rows),
            "model":selection["collection"],"worker_started":bool(rows),
            "public_generation_unchanged":original_generation,
        })
        return result
    except Exception as exc:
        if started:
            try:
                # Even a half-upserted batch is reconciled from Qdrant.
                # Leave a resumable PAUSED job rather than faking success.
                update_auto_checkpoint(
                    queue_path,job_id,token,generation,
                    failure=type(exc).__name__,last="FAILED",
                )
            except Exception:
                # A stale/fenced worker must never force its own checkpoint.
                pass
        raise
    finally:
        event.set()
        if heartbeat is not None:
            heartbeat.join(timeout=5)
        # Release only the exact fenced owner. Never delete stage data.
        release_index_supervisor(queue_path,job_id,token,generation)
