"""Target-project RAG-DEL conflict inventory (read-only, DEV planning only).

An unrelated RAG-AUTO canary need not block *planning* for a distinct private
project, but ANY future shared-catalog change requires its own atomic compare
and swap under the canonical lock. This module NEVER authorizes that change.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


def _read_object(path: Path) -> dict:
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > 1048576):
        raise ValueError("unsafe or unbounded JSON")
    data=json.loads(path.read_text(encoding="utf-8"))
    if type(data) is not dict:
        raise ValueError("invalid JSON object")
    return data


def inspect_project_conflicts_read_only(
    *, project_id: str, catalog_directory: Path, queue_path: Path
) -> dict:
    result=dict(
        state="PROJECT_CONFLICTS_UNVERIFIED", read_only=True,
        project_id=project_id, target_queue_jobs=0,
        target_active_canaries=0, unrelated_queue_jobs=0,
        unrelated_active_canaries=0,
        target_generation_dir=None, catalog_sha256=None,
        public_pointer_sha256=None, catalog_cas_required=True,
        target_isolation_proven=False,
        activation_authorized=False, operational_use_allowed=False,
        blockers=[]
    )
    errors=result["blockers"]
    if not isinstance(project_id,str) or not project_id or project_id=="codebridge":
        errors.append("INVALID_PRIVATE_PROJECT")
        return result
    root=Path(catalog_directory)
    queue_path=Path(queue_path)
    if (not root.is_absolute() or not root.is_dir() or root.is_symlink()
            or any(parent.is_symlink() for parent in root.parents if parent.exists())
            or not queue_path.is_absolute() or queue_path.is_symlink()
            or not queue_path.is_file()):
        errors.append("UNTRUSTED_STORAGE")
        return result
    try:
        catalog_file=root/"project-indexes.json"
        pointer_file=root/"active-generation.json"
        if (not catalog_file.is_file() or catalog_file.is_symlink()
                or not pointer_file.is_file() or pointer_file.is_symlink()):
            raise ValueError("untrusted shared metadata file")
        catalog_raw=catalog_file.read_bytes()
        pointer_raw=pointer_file.read_bytes()
        if len(catalog_raw)>1048576 or len(pointer_raw)>1048576:
            raise ValueError("unbounded shared metadata")
        catalog=json.loads(catalog_raw)
        pointer=json.loads(pointer_raw)
        if type(catalog) is not dict or type(pointer) is not dict:
            raise ValueError("invalid catalog/pointer")
        if (catalog.get("schema_version")!=1
                or pointer.get("schema_version")!=1
                or type(pointer.get("generation")) is not str
                or not pointer["generation"]):
            raise ValueError("invalid schema or public pointer")
        projects=catalog.get("projects")
        if not isinstance(projects,dict) or project_id not in projects:
            errors.append("TARGET_NOT_PRESENT_IN_PRIVATE_CATALOG")
            return result
        target=projects[project_id]
        if not isinstance(target,dict) or target.get("enabled") is not True:
            errors.append("TARGET_PRIVATE_PROJECT_DISABLED")
            return result
        def generation_path(project):
            if type(project) is not dict or type(project.get("generation_directory")) is not str:
                raise ValueError("malformed project generation")
            path=Path(project["generation_directory"])
            if not path.is_absolute() or not path.is_dir() or path.is_symlink():
                raise ValueError("unsafe project generation")
            return path.resolve()
        target_dir=generation_path(target)
        result["target_generation_dir"]=str(target_dir)
        for other_name,other in projects.items():
            if other_name==project_id:
                continue
            other_dir=generation_path(other)
            if target_dir==other_dir or target_dir in other_dir.parents or other_dir in target_dir.parents:
                errors.append("GENERATION_DIRECTORIES_OVERLAP")
                return result
        result["catalog_sha256"]=hashlib.sha256(catalog_raw).hexdigest()
        result["public_pointer_sha256"]=hashlib.sha256(pointer_raw).hexdigest()
        with closing(sqlite3.connect(queue_path.as_uri()+"?mode=ro",
                                     uri=True,timeout=.5)) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA user_version").fetchone()[0]!=1:
                raise ValueError("queue schema changed")
            rows=db.execute(
                "SELECT job_id,project_id,state FROM auto_jobs "
                "WHERE state NOT IN ('CANCELLED','FAILED') LIMIT 102"
            ).fetchall()
            if len(rows)>101:
                raise ValueError("unbounded queue")
        active_jobs=set()
        for job_id, project, state in rows:
            if type(job_id) is not str or type(project) is not str or type(state) is not str:
                raise ValueError("invalid queue row")
            active_jobs.add((job_id,project))
            key="target_queue_jobs" if project==project_id else "unrelated_queue_jobs"
            result[key]+=1
        journals=sorted(root.glob("auto-canary-*.journal.json"))
        if len(journals)>100:
            raise ValueError("unbounded canaries")
        for path in journals:
            row=_read_object(path)
            project=row.get("project_id")
            job=row.get("job_id")
            if (row.get("schema_version")!=1 or row.get("state")!="CANARY_ACTIVE"
                    or type(job) is not str or type(project) is not str
                    or len(job)!=32
                    or path.name!=f"auto-canary-{job}.journal.json"
                    or row.get("catalog")!=str(catalog_file)
                    or row.get("new_sha256")!=result["catalog_sha256"]
                    or row.get("public_pointer_sha256")!=result["public_pointer_sha256"]):
                raise ValueError("canary pointer changed")
            backup=Path(row.get("backup",""))
            if (backup!=root/f"auto-canary-{job}.previous.json"
                or not backup.is_file() or backup.is_symlink()
                or backup.stat().st_size>1048576
                or hashlib.sha256(backup.read_bytes()).hexdigest()!=row.get("old_sha256")
                or (job,project) not in active_jobs
                or project not in projects
                or projects[project].get("job_id")!=job):
                raise ValueError("canary journal/queue/catalog misaligned")
            key=("target_active_canaries" if project==project_id
                 else "unrelated_active_canaries")
            result[key]+=1
        # Re-read key global sources after inventory; any mid-read mutation denies.
        with closing(sqlite3.connect(queue_path.as_uri()+"?mode=ro",
                                     uri=True,timeout=.5)) as db:
            db.execute("PRAGMA query_only=ON")
            latest=db.execute(
                "SELECT job_id,project_id,state FROM auto_jobs "
                "WHERE state NOT IN ('CANCELLED','FAILED') LIMIT 102"
            ).fetchall()
        if sorted(latest)!=sorted(rows):
            raise ValueError("queue changed during inspection")
        if (hashlib.sha256(catalog_file.read_bytes()).hexdigest()!=result["catalog_sha256"]
                or hashlib.sha256(pointer_file.read_bytes()).hexdigest()!=result["public_pointer_sha256"]):
            raise ValueError("catalog or pointer changed during inspection")
        if result["target_queue_jobs"]:
            errors.append("TARGET_QUEUE_JOB_ACTIVE")
        if result["target_active_canaries"]:
            errors.append("TARGET_CANARY_ACTIVE")
        if errors:
            result["state"]="TARGET_PROJECT_BLOCKED"
        else:
            # An unrelated canary is not to be rolled back for this target,
            # but the shared catalog still requires lock + CAS on any write.
            result["target_isolation_proven"]=True
            result["state"]="TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING"
    except (OSError,ValueError,TypeError,sqlite3.Error,UnicodeError,KeyError):
        errors.append("PROJECT_CONFLICT_INVENTORY_UNVERIFIED")
    return result
