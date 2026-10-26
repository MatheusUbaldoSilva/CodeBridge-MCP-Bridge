"""RAG-AUTO-02.5: bounded, operator-started batch loop.

Entry point for a dedicated supervised Python process. A call is finite,
honors durable queue control requests, and NEVER publishes a generation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from rag.runtime.auto_index_queue import get_job,default_queue_path
from rag.runtime.auto_index_worker import execute_auto_vector_batch


def run_approved_auto_job(queue_path: Path,job_id: str, *,
                          execute: bool=False,operator_approved: bool=False,
                          confirmation: str|None=None,
                          max_batches: int=96,batch_size: int=256,
                          prefer: str="TEXT",run_batch=None) -> dict:
    if execute is not True or operator_approved is not True or (
        confirmation!="RAG_AUTO_RUN:"+job_id
    ):
        raise PermissionError("explicit job-specific runner approval required")
    if type(max_batches) is not int or not 1<=max_batches<=10000:
        raise ValueError("invalid maximum batch count")
    if type(batch_size) is not int or not 1<=batch_size<=256:
        raise ValueError("invalid batch size")
    job=get_job(queue_path,job_id)
    if job is None or not job["approved"] or job["state"]!="QUEUED":
        raise ValueError("only an approved queued job can start a worker")
    runner=execute_auto_vector_batch if run_batch is None else run_batch
    completed=0
    records=[]
    for number in range(1,max_batches+1):
        state=get_job(queue_path,job_id)
        if state is None or state["state"]!="QUEUED":
            return {
                "job_id":job_id,"state":state["state"] if state else "NOT_FOUND",
                "batches":completed,"index_published":False,
                "run_ended":"STATE_CHANGED",
            }
        record=runner(
            queue_path,job_id,execute=True,operator_approved=True,
            confirmation="RAG_AUTO_RUN:"+job_id,
            max_vectors=batch_size,prefer=prefer,
        )
        completed+=1
        records.append({
            "number":number,
            "state":record["state"],
            "vectors_done":record.get("vectors_done"),
            "vectors_expected":record.get("vectors_expected"),
        })
        if record["state"]!="QUEUED":
            return {
                "job_id":job_id,"state":record["state"],
                "batches":completed,"index_published":False,
                "run_ended":"JOB_CHECKPOINT",
                "last":records[-1],
            }
    return {
        "job_id":job_id,"state":get_job(queue_path,job_id)["state"],
        "batches":completed,"index_published":False,
        "run_ended":"BOUNDED_LIMIT_REACHED","last":records[-1],
    }


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(
        description="RAG-AUTO isolated job runner; no production publication"
    )
    parser.add_argument("--job-id",required=True)
    parser.add_argument("--queue-path",default=str(default_queue_path()))
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--operator-approved",action="store_true")
    parser.add_argument("--confirmation",required=True)
    parser.add_argument("--batch-size",type=int,default=256)
    parser.add_argument("--max-batches",type=int,default=96)
    parser.add_argument("--prefer",choices=("TEXT","CODE"),default="TEXT")
    options=parser.parse_args(argv)
    answer=run_approved_auto_job(
        Path(options.queue_path),options.job_id,
        execute=options.execute,operator_approved=options.operator_approved,
        confirmation=options.confirmation,
        max_batches=options.max_batches,batch_size=options.batch_size,
        prefer=options.prefer,
    )
    print(json.dumps(answer,sort_keys=True,ensure_ascii=False),flush=True)
    return 0 if answer["state"] in (
        "READY_FOR_REVIEW","QUEUED","PAUSED","CANCELLED","WAITING_FOR_MEMORY",
    ) else 2


if __name__=="__main__":
    raise SystemExit(main())
