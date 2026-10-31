"""DQ-E-F-5: read-only unresolved AUTO job evidence, no approval or mutation."""
from __future__ import annotations
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3
from rag.runtime.auto_index_queue import _canonical_queue_path

def inspect_pending_review_jobs_dev(path:Path)->dict:
    result=dict(state="AUTO_REVIEW_JOBS_BLOCKED_READ_ONLY",
        read_only=True,activation_authorized=False,operational_use_allowed=False,
        pending_jobs=[],blockers=[])
    try:
        path=_canonical_queue_path(Path(path))
        if not path.is_file() or path.is_symlink():
            raise ValueError("invalid queue path")
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=0.5)) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA user_version").fetchone()[0]!=1:
                raise ValueError("invalid queue schema")
            states=db.execute("""SELECT job_id,project_id,state,approved,
                candidate_generation FROM auto_jobs
                WHERE state NOT IN ('CANCELLED','FAILED')
                ORDER BY job_id LIMIT 101""").fetchall()
            if len(states)>100:
                raise ValueError("job inventory exceeds read-only limit")
            for job_id,project,state,approved,generation in states:
                if not isinstance(job_id,str) or not isinstance(project,str):
                    raise ValueError("malformed queue job")
                result["pending_jobs"].append(dict(
                    job_sha256=sha256(job_id.encode()).hexdigest(),
                    project_sha256=sha256(project.encode()).hexdigest(),
                    state=state,approved=approved==1,
                    has_candidate=isinstance(generation,str) and bool(generation),
                ))
    except (OSError,sqlite3.Error,ValueError,TypeError):
        result["blockers"].append("QUEUE_READ_UNVERIFIED")
        return result
    if result["pending_jobs"]:
        result["blockers"].append("PENDING_REVIEW_JOBS_PRESENT")
    else:
        result["state"]="AUTO_REVIEW_QUEUE_INVENTORY_EMPTY_READ_ONLY"
    return result
