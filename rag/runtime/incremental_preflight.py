"""Read-only assessment before adding files to an existing RAG project.

No publishing or embedding is performed by this module.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from rag.runtime.status import resolve_rag_sqlite_path


def assess_incremental_plan(plan: dict, *, database: Path | None = None) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("invalid index plan")
    project = plan.get("project_id")
    if not isinstance(project, str) or not project:
        raise ValueError("project_id is required")
    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    db = Path(database) if database is not None else resolve_rag_sqlite_path()
    existing = set()
    if db.exists():
        connection = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            existing = {str(row[0]) for row in connection.execute(
                "SELECT path FROM rag_documents WHERE project_id=? AND path IS NOT NULL",
                (project,),
            )}
        finally:
            connection.close()
    fresh = []
    duplicates = []
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("invalid candidate")
        path = item["path"]
        (duplicates if path in existing else fresh).append(path)
    return {
        "project_id": project,
        "new_count": len(fresh),
        "existing_count": len(duplicates),
        "new_files": fresh,
        "existing_files": duplicates,
        "safe_to_publish": False,
        "reason": "A publicacao incremental ainda nao foi implementada e validada.",
    }
