"""Read-only operational RAG-DEL queue/canary reconciliation for CLOSE-03.

Reads real files when explicitly called, never updates queue, journal or
catalog, and never authorizes operational deletion. Not a trusted GUI/IPC
attestation.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from rag.runtime.auto_index_queue import _canonical_queue_path
from rag.runtime.knowledge_deletion_journal_inventory_dev import (
    inspect_deletion_journals_read_only,
)
from rag.runtime.knowledge_deletion_queue_review_inventory_dev import (
    inspect_pending_review_jobs_dev,
)


def _json_object_read_only(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1048576:
        raise ValueError("missing, redirected or oversized JSON")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def reconcile_operational_generation_read_only(
    catalog_directory: Path, queue_path: Path
) -> dict:
    """Fail-closed read-only inventory. Evidence alone cannot enable deletion."""
    directory = Path(catalog_directory)
    result = {
        "state": "CLOSE03_OPERATIONAL_EVIDENCE_BLOCKED",
        "read_only": True,
        "activation_authorized": False,
        "operational_use_allowed": False,
        "ready_for_operational_pilot": False,
        "public_generation": None,
        "queue_pending_count": None,
        "canary_count": None,
        "canary_catalog_consistent": False,
        "matched_canary_queue_job": False,
        "blockers": [],
    }
    blockers = result["blockers"]
    if (not directory.is_absolute() or not directory.is_dir()
        or directory.is_symlink()
        or (hasattr(directory, "is_junction") and directory.is_junction())
        or any(parent.is_symlink() for parent in directory.parents if parent.exists())):
        blockers.append("UNTRUSTED_CATALOG_DIRECTORY")
        return result
    journal = inspect_deletion_journals_read_only(directory)
    if journal["state"] != "DELETION_JOURNAL_INVENTORY_READ_ONLY_CLEAN":
        blockers.append("DELETION_JOURNALS_NOT_CLEAN")
    queue_review = inspect_pending_review_jobs_dev(queue_path)
    if "QUEUE_READ_UNVERIFIED" in queue_review["blockers"]:
        blockers.append("QUEUE_READ_UNVERIFIED")
        return result
    result["queue_pending_count"] = len(queue_review["pending_jobs"])
    try:
        queue_path = _canonical_queue_path(Path(queue_path))
        with closing(sqlite3.connect(queue_path.as_uri()+"?mode=ro",
                                     uri=True, timeout=0.5)) as db:
            db.execute("PRAGMA query_only=ON")
            pending = db.execute(
                "SELECT job_id,project_id,state,approved,candidate_generation FROM auto_jobs "
                "WHERE state NOT IN ('CANCELLED','FAILED') ORDER BY job_id LIMIT 101"
            ).fetchall()
        actual_receipts = [dict(
            job_sha256=hashlib.sha256(job_id.encode()).hexdigest(),
            project_sha256=hashlib.sha256(project_id.encode()).hexdigest(),
            state=state, approved=approved == 1,
            has_candidate=isinstance(candidate,str) and bool(candidate)
        ) for job_id,project_id,state,approved,candidate in pending]
        if actual_receipts != queue_review["pending_jobs"]:
            raise ValueError("queue changed between reads")
        catalog_path = directory / "project-indexes.json"
        catalog = _json_object_read_only(catalog_path)
        pointer = _json_object_read_only(directory / "active-generation.json")
        generation = pointer.get("generation")
        if pointer.get("schema_version") != 1 or not isinstance(generation,str) or not generation:
            raise ValueError("invalid public pointer")
        result["public_generation"] = generation
        projects = catalog.get("projects")
        if catalog.get("schema_version") != 1 or not isinstance(projects,dict):
            raise ValueError("invalid project catalog")
        journals = sorted(directory.glob("auto-canary-*.journal.json"))
        if len(journals) > 100:
            raise ValueError("unbounded canary journals")
        result["canary_count"] = len(journals)
        matched = []
        catalog_hash = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        for path in journals:
            record = _json_object_read_only(path)
            backup = Path(record.get("backup",""))
            project_id,job_id = record.get("project_id"),record.get("job_id")
            project = projects.get(project_id) if isinstance(project_id,str) else None
            if (record.get("state") != "CANARY_ACTIVE"
                or not isinstance(job_id,str) or len(job_id) != 32
                or path.name != f"auto-canary-{job_id}.journal.json"
                or record.get("catalog") != str(catalog_path)
                or catalog_hash != record.get("new_sha256")
                or not backup.is_file() or backup.is_symlink()
                or hashlib.sha256(backup.read_bytes()).hexdigest() != record.get("old_sha256")
                or not isinstance(project,dict)
                or project.get("job_id") != job_id
                or not Path(project.get("generation_directory","")).is_dir()):
                blockers.append("CANARY_CATALOG_INCONSISTENT")
                continue
            matched.append((job_id,project_id))
        result["canary_catalog_consistent"] = len(matched) == len(journals)
        for job_id,project_id,state,approved,candidate in pending:
            if not isinstance(job_id,str) or not isinstance(project_id,str):
                blockers.append("MALFORMED_PENDING_QUEUE_JOB")
                continue
            if (job_id,project_id) in matched and state == "READY_FOR_REVIEW" and (
                not isinstance(candidate,str) or not Path(candidate).is_dir()
            ):
                blockers.append("CANARY_CANDIDATE_MISSING")
            if (job_id,project_id) in matched:
                result["matched_canary_queue_job"] = True
        if pending:
            blockers.append("QUEUE_PENDING_OPERATOR_REVIEW_REQUIRED")
        if journals:
            blockers.append("ACTIVE_CANARY_OPERATOR_REVIEW_REQUIRED")
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, json.JSONDecodeError):
        blockers.append("OPERATIONAL_EVIDENCE_UNVERIFIED")
    if not blockers:
        result["state"] = "CLOSE03_READONLY_QUEUE_CANARY_QUIET_UNTRUSTED_IPC"
    return result
