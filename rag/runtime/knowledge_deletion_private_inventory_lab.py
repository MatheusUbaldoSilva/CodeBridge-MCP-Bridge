"""RAG-DEL-01.04-DM: private document inventory under scratch catalog writer lock.

This is NOT a production private reader: it is restricted to TemporaryDirectory
fixtures, and currently only proves cooperation with the lab catalog mutex.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab, LaboratoryCatalogUnsafe,
)
from rag.runtime.knowledge_deletion_swap_lab import _lab_paths


class PrivateInventoryLabError(RuntimeError):
    pass


@contextmanager
def _private_lab_catalog_guard(catalog: Path):
    """Keep the previous DM unsafe-catalog exception contract."""
    try:
        with bounded_catalog_mutex_lab(
            catalog, laboratory_mode=True, operator_approved=True,
        ):
            yield
    except LaboratoryCatalogUnsafe as exc:
        raise PrivateInventoryLabError(str(exc)) from exc


def laboratory_private_inventory_locked(
    project_id: str,
    *, catalog_file: Path, sqlite_path: Path,
    operator_approved: bool = False, laboratory_mode: bool = False,
) -> dict:
    """Observe scratch private documents while preventing cooperative CAS."""
    if operator_approved is not True or laboratory_mode is not True:
        raise PermissionError("explicit scratch private-inventory approval required")
    if (not isinstance(project_id, str) or not project_id
            or project_id == "codebridge"):
        raise PrivateInventoryLabError("public or invalid project not accepted")
    catalog = Path(catalog_file).absolute()
    # Reuse strict scratch-only catalog validation enforced by lab swap.
    _lab_paths(catalog, catalog.parent / "active-generation.json")
    folder = catalog.parent.resolve(strict=True)
    sqlite = Path(sqlite_path).absolute()
    if (not sqlite.is_file() or sqlite.is_symlink()
            or sqlite.name != "rag_index.sqlite3"
            or not sqlite.resolve(strict=True).is_relative_to(folder)
            or folder == sqlite.parent.resolve()
            or any(p.is_symlink() or (
                hasattr(p, "is_junction") and p.is_junction()
            ) for p in (sqlite, sqlite.parent, sqlite.parent.parent))):
        raise PrivateInventoryLabError("invalid scratch private SQLite")
    with _private_lab_catalog_guard(catalog):
        for pending in folder.glob("rag-del-*.journal.json"):
            # Even a historical journal is rejected in this conservative
            # preview; recovery should occur before a new inventory audit.
            if pending.exists() or pending.is_symlink():
                raise PrivateInventoryLabError("unreconciled deletion journal")
        before = catalog.read_bytes()
        data = json.loads(before.decode("utf-8-sig"))
        if (data.get("schema_version") != 1
                or not isinstance(data.get("projects"), dict)):
            raise PrivateInventoryLabError("bad scratch catalog")
        row = data["projects"].get(project_id)
        if (not isinstance(row, dict) or row.get("enabled") is not True
                or row.get("project_id") != project_id
                or Path(row.get("generation_directory", "")).resolve()
                != sqlite.parent.resolve()
                or not isinstance(row.get("sqlite_sha256"), str)
                or len(row["sqlite_sha256"]) != 64):
            raise PrivateInventoryLabError("untrusted private catalog row")
        digest = sha256(sqlite.read_bytes()).hexdigest()
        if digest != row["sqlite_sha256"]:
            raise PrivateInventoryLabError("private index fingerprint drift")
        with closing(sqlite3.connect(
            sqlite.resolve().as_uri() + "?mode=ro",
            uri=True, isolation_level=None, timeout=5,
        )) as db:
            db.execute("PRAGMA query_only=ON")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise PrivateInventoryLabError("private SQLite integrity failure")
            items = db.execute(
                "SELECT path,COUNT(*),MAX(source_type) "
                "FROM rag_documents WHERE project_id=? "
                "GROUP BY path ORDER BY path LIMIT 2000",
                (project_id,),
            ).fetchall()
        if (catalog.read_bytes() != before
                or sha256(sqlite.read_bytes()).hexdigest() != digest):
            raise PrivateInventoryLabError("private inventory changed during read")
    return {
        "state": "LAB_PRIVATE_INVENTORY_READ_ONLY",
        "project_id": project_id,
        "documents": [
            {"path": path, "count": count, "type": kind}
            for path, count, kind in items
        ],
        "catalog_sha256": sha256(before).hexdigest(),
        "sqlite_sha256": digest,
        "activation_authorized": False,
        "operational_use_allowed": False,
        "read_only": True,
    }