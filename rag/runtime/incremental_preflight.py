"""Read-only file-level classification before incremental RAG indexing.

This module never opens production SQLite in write mode or changes vectors.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from rag.chunking.provenance import source_sha256
from rag.runtime.status import resolve_rag_sqlite_path


def assess_incremental_plan(plan: dict, *, database: Path | None = None) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("invalid index plan")
    project = plan.get("project_id")
    if not isinstance(project, str) or not project:
        raise ValueError("project_id is required")
    candidates = plan.get("candidates")
    root_value = plan.get("project_root")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    # Existing tests and integrations may supply a plan without a project root:
    # in that case only name-based classification is possible.
    root = Path(root_value).resolve() if isinstance(root_value, str) and root_value else None
    db = Path(database) if database is not None else resolve_rag_sqlite_path()
    existing: dict[str, str | None] = {}
    if db.exists():
        connection = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            existing = {
                str(row[0]): row[1]
                for row in connection.execute(
                    "SELECT path, sha256 FROM rag_documents "
                    "WHERE project_id=? AND path IS NOT NULL", (project,)
                )
            }
        finally:
            connection.close()

    fresh, unchanged, modified, unknown = [], [], [], []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("invalid candidate")
        path = item["path"]
        if not path or path in seen:
            raise ValueError("empty or duplicate candidate path")
        seen.add(path)
        if path not in existing:
            fresh.append(path)
            continue
        if root is None or not existing[path]:
            unknown.append(path)
            continue
        file = (root / path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError("candidate missing or outside project root")
        digest = source_sha256(file.read_text(encoding="utf-8", errors="replace"))
        (unchanged if digest == existing[path] else modified).append(path)
    return {
        "project_id": project,
        "new_count": len(fresh),
        "existing_count": len(unchanged) + len(modified) + len(unknown),
        "unchanged_count": len(unchanged),
        "modified_count": len(modified),
        "unknown_count": len(unknown),
        "new_files": fresh,
        "existing_files": unchanged + modified + unknown,
        "unchanged_files": unchanged,
        "modified_files": modified,
        "unknown_files": unknown,
        "safe_to_publish": False,
        "reason": "A publicacao incremental ainda nao foi implementada e validada.",
    }
