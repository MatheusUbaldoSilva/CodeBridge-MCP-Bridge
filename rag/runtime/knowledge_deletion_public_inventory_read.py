"""RAG-DEL-01.04-DJ: pinned public document inventory for future GUI migration.

Read-only, public-codebridge namespace only. Does not activate deletion or
replace any installed GUI path without a separate, reviewed integration.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from rag.runtime.production_generation_read import production_generation_read


def read_pinned_public_document_inventory(
    *, project_id: str = "codebridge", limit: int = 2000,
) -> dict:
    """Read a coherent public inventory inside the generation shared lock."""
    if project_id != "codebridge":
        raise ValueError("private project inventory needs isolated project guard")
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("inventory limit must be 1..2000")
    with production_generation_read() as pinned:
        db = Path(pinned.sqlite)
        if (db.is_symlink()
                or (hasattr(db, "is_junction") and db.is_junction())):
            raise RuntimeError("redirected public SQLite inventory")
        with closing(sqlite3.connect(
            db.resolve().as_uri() + "?mode=ro",
            uri=True, timeout=10, isolation_level=None,
        )) as cn:
            cn.execute("PRAGMA query_only=ON")
            rows = cn.execute(
                "SELECT path,COUNT(*),MAX(source_type) "
                "FROM rag_documents WHERE project_id=? "
                "GROUP BY path ORDER BY path LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return {
            "state": "PUBLIC_DOCUMENT_INVENTORY_READ_ONLY",
            "generation": pinned.generation,
            "project_id": project_id,
            "documents": [
                {"path": path, "count": count, "type": kind}
                for path, count, kind in rows
            ],
            "read_only": True,
            "activation_authorized": False,
            "operational_use_allowed": False,
        }