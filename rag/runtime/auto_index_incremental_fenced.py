"""RAG-AUTO-05-F: fenced incremental worker with periodic lease heartbeat.

No automatic reservation, generation promotion, or unattended retry. A lost
lease aborts the success path and requires isolated-stage audit.
"""
from __future__ import annotations

from pathlib import Path
import threading

from rag.runtime.auto_index_supervisor import renew_index_supervisor
from rag.runtime.auto_index_incremental_transfer import transfer_verified_incremental_batch
from rag.runtime.production_generation_lock import production_generation_lock


def execute_fenced_incremental_batch(
    queue_path: Path, baseline_job_id: str, candidate_job_id: str, *,
    lease_token: str, generation: int,
    operator_approved: bool = False, max_vectors: int = 256,
    heartbeat_seconds: float = 20.0, batch_index: int = 0,
    **model_revisions: str,
) -> dict:
    if operator_approved is not True:
        raise PermissionError("explicit incremental execution approval required")
    if (not isinstance(lease_token, str) or len(lease_token) != 32
            or any(c not in "0123456789abcdef" for c in lease_token)):
        raise PermissionError("valid fenced lease token required")
    if type(batch_index) is not int or batch_index < 0:
        raise ValueError("nonnegative integer batch_index required")
    if type(generation) is not int or generation < 1:
        raise PermissionError("fenced lease generation required")
    if (type(heartbeat_seconds) not in (int, float)
            or not 1 <= heartbeat_seconds <= 60):
        raise ValueError("heartbeat must be between 1 and 60 seconds")
    def renew():
        return renew_index_supervisor(
            queue_path, candidate_job_id, lease_token, generation,
            lease_seconds=3600,
        )
    first = renew()
    if first.get("accepted") is not True:
        raise PermissionError("supervisor lease is not owned")
    stop = threading.Event()
    lost = threading.Event()
    def heartbeat():
        while not stop.wait(heartbeat_seconds):
            try:
                if renew().get("accepted") is not True:
                    lost.set()
                    return
            except Exception:
                lost.set()
                return
    worker = threading.Thread(
        target=heartbeat, name="ragauto05-lease-heartbeat", daemon=True,
    )
    worker.start()
    try:
        with production_generation_lock(exclusive=True, channel="semantic"):
            if lost.is_set():
                raise RuntimeError("supervisor fencing lost before import")
            result = transfer_verified_incremental_batch(
                queue_path, baseline_job_id, candidate_job_id,
                operator_approved=True, max_vectors=max_vectors,
                batch_index=batch_index,
                **model_revisions,
            )
            if lost.is_set() or renew().get("accepted") is not True:
                raise RuntimeError(
                    "supervisor fencing lost during incremental batch; stage must be audited"
                )
        return {
            **result,
            "supervisor_fence_rechecked": True,
            "stage_revalidation_required": True,
            "public_pointer_updated": False,
        }
    finally:
        stop.set()
        worker.join(timeout=5)
