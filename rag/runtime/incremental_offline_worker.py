"""Opt-in single-step V1.03-D-C offline consumer. No daemon or scheduler.

Call from an application-managed process only after operator opt-in.
Never publishes a generation or modifies the active RAG index.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable
from threading import Event, Thread

from rag.runtime.incremental_job_queue import (
    claim_approved_job, acknowledge_staged_bundle, report_staging_failure,
    renew_job_lease,
)
from rag.runtime.index_request import RagIndexScope, plan_rag_index


def process_offline_job_once(
    db_path: Path, project_root: Path, *,
    approved_paths: Iterable[str] = (),
    queue_enabled: bool = False, worker_enabled: bool = False,
    builder: Callable | None = None,
    now_epoch: float | None = None,
    heartbeat_interval_seconds: float = 30,
) -> dict:
    """One reservation and one isolated staging attempt; never loops."""
    if queue_enabled is not True or worker_enabled is not True:
        return {"state": "OFFLINE_WORKER_DISABLED", "executed": False,
                "safe_to_publish": False, "active_index_updated": False}
    if not 0.01 <= heartbeat_interval_seconds <= 30:
        return {"state": "INVALID_HEARTBEAT_POLICY", "executed": False,
                "safe_to_publish": False, "active_index_updated": False}
    approved = tuple(approved_paths)
    claim = claim_approved_job(
        db_path, project_root, approved_paths=approved,
        now_epoch=now_epoch, queue_enabled=True,
    )
    if not claim.get("claimed"):
        return claim
    job_id, token = claim["job_id"], claim["lease_token"]
    heartbeat_stop = Event()
    lease_lost = Event()
    def heartbeat():
        while not heartbeat_stop.wait(heartbeat_interval_seconds):
            try:
                renewed = renew_job_lease(
                    db_path, job_id, token, queue_enabled=True,
                    lease_seconds=120,
                )
                if not renewed.get("renewed"):
                    lease_lost.set()
                    return
            except Exception:
                lease_lost.set()
                return
    thread = None
    if now_epoch is None:
        thread = Thread(target=heartbeat, name="rag-offline-lease", daemon=True)
        thread.start()
    try:
        planned = plan_rag_index(
            "codebridge", project_root, scope=RagIndexScope.BOTH,
            paths=(claim["source_path"],),
        )
        if (planned.candidate_count != 1 or
                planned.candidates[0].path != claim["source_path"]):
            raise ValueError("approved job has no eligible unique candidate")
        if builder is None:
            from rag.runtime.production_index import build_staged_index
            builder = build_staged_index
        staged = builder(planned)
        if staged.get("state") != "STAGED_NOT_PUBLISHED":
            raise ValueError("builder did not return isolated staging")
        if lease_lost.is_set():
            raise RuntimeError("worker lease lost during staging")
        outcome = acknowledge_staged_bundle(
            db_path, project_root, job_id, token, Path(staged["staging_path"]),
            approved_paths=approved, now_epoch=now_epoch, queue_enabled=True,
        )
        if not outcome.get("acknowledged"):
            report_staging_failure(
                db_path, job_id, token, reason="OFFLINE_VALIDATION_REJECTED",
                now_epoch=now_epoch, queue_enabled=True,
            )
        return {k: v for k, v in outcome.items() if k != "lease_token"}
    except Exception as exc:
        # Reason is structural only; no source content or credentials in status.
        failure = report_staging_failure(
            db_path, job_id, token, reason="OFFLINE_BUILD_" + type(exc).__name__,
            now_epoch=now_epoch, queue_enabled=True,
        )
        return {"state": failure["state"], "error_type": type(exc).__name__,
                "executed": False, "safe_to_publish": False,
                "active_index_updated": False}
    finally:
        heartbeat_stop.set()
        if thread is not None:
            thread.join(timeout=5)


def main(argv=None) -> int:
    """One-shot standalone entrypoint. No scheduler and no implicit enablement."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="CodeBridge offline RAG staging worker")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--approved-path", action="append", default=[])
    parser.add_argument("--enable-queue", action="store_true")
    parser.add_argument("--enable-offline-worker", action="store_true")
    args = parser.parse_args(argv)
    response = process_offline_job_once(
        Path(args.db_path), Path(args.project_root),
        approved_paths=args.approved_path,
        queue_enabled=args.enable_queue,
        worker_enabled=args.enable_offline_worker,
    )
    print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    return 0 if response.get("state") in (
        "OFFLINE_WORKER_DISABLED", "QUEUE_EMPTY",
        "STAGED_OFFLINE_VALIDATED", "AUTO_INDEX_DISABLED",
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
