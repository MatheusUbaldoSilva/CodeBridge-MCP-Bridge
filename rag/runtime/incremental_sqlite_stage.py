"""Build a SQLite-only incremental candidate in an isolated destination.

Never modifies input databases. Does not publish or change Qdrant/manifest.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path


class IncrementalSqliteStageError(RuntimeError):
    pass


def stage_incremental_sqlite(existing_db, new_db, destination, project_id):
    source = Path(existing_db).resolve()
    stage = Path(new_db).resolve()
    output = Path(destination).resolve()
    if output.exists() or len({source, stage, output}) != 3:
        raise IncrementalSqliteStageError("destination must be new and distinct")
    if not source.is_file() or not stage.is_file():
        raise IncrementalSqliteStageError("both SQLite indexes must exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(output)
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    dest = sqlite3.connect(output, uri=True)
    try:
        dest.execute("PRAGMA foreign_keys=ON")
        dest.execute("ATTACH DATABASE ? AS candidate", (stage.as_uri() + "?mode=ro",))
        schema = ("rag_documents", "rag_chunks", "rag_chunk_symbols")
        for table in schema:
            dest_cols = {r[1] for r in dest.execute(f"PRAGMA table_info({table})")}
            stage_cols = {r[1] for r in dest.execute(f"PRAGMA candidate.table_info({table})")}
            if dest_cols != stage_cols:
                raise IncrementalSqliteStageError(f"incompatible schema: {table}")
        incoming = dest.execute(
            "SELECT document_id, path FROM candidate.rag_documents WHERE project_id=?",
            (project_id,),
        ).fetchall()
        if not incoming:
            raise IncrementalSqliteStageError("empty candidate project")
        if len(incoming) != dest.execute("SELECT count(*) FROM candidate.rag_documents").fetchone()[0]:
            raise IncrementalSqliteStageError("candidate contains a different project")
        existing_docs = {r[0] for r in dest.execute(
            "SELECT document_id FROM rag_documents WHERE project_id=?", (project_id,))}
        incoming_ids = {r[0] for r in incoming}
        replaced = existing_docs & incoming_ids
        with dest:
            # Old data is removed only from the isolated copy.
            for did in replaced:
                dest.execute("DELETE FROM rag_chunk_symbols WHERE chunk_id IN "
                             "(SELECT chunk_id FROM rag_chunks WHERE document_id=?)", (did,))
                dest.execute("DELETE FROM rag_chunks WHERE document_id=?", (did,))
                dest.execute("DELETE FROM rag_documents WHERE document_id=?", (did,))
            for table in schema:
                cols = [r[1] for r in dest.execute(f"PRAGMA table_info({table})")]
                names = ", ".join('"' + name + '"' for name in cols)
                if table == "rag_documents":
                    query = f"SELECT {names} FROM candidate.{table} WHERE project_id=?"
                elif table == "rag_chunks":
                    query = f"SELECT {names} FROM candidate.{table} WHERE project_id=?"
                else:
                    query = (f"SELECT {names} FROM candidate.{table} WHERE chunk_id IN "
                             "(SELECT chunk_id FROM candidate.rag_chunks WHERE project_id=?)")
                rows = dest.execute(query, (project_id,)).fetchall()
                placeholders = ", ".join("?" for _ in cols)
                dest.executemany(
                    f"INSERT INTO {table} ({names}) VALUES ({placeholders})", rows)
            from rag.index.fts5 import initialize_fts5
            initialize_fts5(dest, rebuild=True)
            integrity = dest.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise IncrementalSqliteStageError("merged SQLite integrity failure")
        total = dest.execute("SELECT count(*) FROM rag_documents").fetchone()[0]
        return {"state": "SQLITE_STAGED_NOT_PUBLISHED",
                "project_id": project_id, "added": len(incoming_ids - replaced),
                "replaced": len(replaced), "total_documents": total,
                "destination": str(output)}
    except BaseException:
        dest.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        try:
            dest.close()
        except Exception:
            pass
