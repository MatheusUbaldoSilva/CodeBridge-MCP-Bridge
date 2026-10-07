"""FTS5 projection for the CodeBridge RAG text index — RAG-005-B.

The relational SQLite tables remain the persistent source for the index.
FTS5 is an explicitly initialized, rebuildable projection over rag_chunks
and rag_chunk_symbols. This module does not implement the public lexical
search API or ranking policy; those belong to RAG-005-C and RAG-005-D.
"""

from __future__ import annotations

import sqlite3
from typing import FrozenSet

from .sqlite_schema import initialize_rag_schema


FTS_LAYOUT_VERSION = 1
FTS_TABLE = "rag_chunks_fts"

FTS_INDEXED_FIELDS: FrozenSet[str] = frozenset({
    "content",
    "path",
    "symbol",
    "git_message",
    "title",
    "heading_path",
})

FTS_METADATA_FIELDS: FrozenSet[str] = frozenset({
    "chunk_id",
    "document_id",
    "project_id",
})

REQUIRED_FTS_TRIGGERS: FrozenSet[str] = frozenset({
    "rag_chunks_ai_fts",
    "rag_chunks_au_fts",
    "rag_chunks_ad_fts",
    "rag_chunk_symbols_ai_fts",
    "rag_chunk_symbols_au_fts",
    "rag_chunk_symbols_ad_fts",
})


class RagFts5UnavailableError(RuntimeError):
    pass


class RagFts5IntegrityError(RuntimeError):
    pass


_FTS_CREATE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts
USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    project_id UNINDEXED,
    content,
    path,
    symbol,
    git_message,
    title,
    heading_path,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


_FTS_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS rag_chunks_ai_fts
AFTER INSERT ON rag_chunks
BEGIN
    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    VALUES (
        NEW.rowid,
        NEW.chunk_id,
        NEW.document_id,
        NEW.project_id,
        NEW.content,
        COALESCE(NEW.path, ''),
        trim(
            COALESCE(NEW.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = NEW.chunk_id
                ),
                ''
            )
        ),
        COALESCE(NEW.git_message, ''),
        COALESCE(NEW.title, ''),
        COALESCE(NEW.heading_path, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS rag_chunks_au_fts
AFTER UPDATE ON rag_chunks
BEGIN
    DELETE FROM rag_chunks_fts
    WHERE rowid = OLD.rowid;

    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    VALUES (
        NEW.rowid,
        NEW.chunk_id,
        NEW.document_id,
        NEW.project_id,
        NEW.content,
        COALESCE(NEW.path, ''),
        trim(
            COALESCE(NEW.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = NEW.chunk_id
                ),
                ''
            )
        ),
        COALESCE(NEW.git_message, ''),
        COALESCE(NEW.title, ''),
        COALESCE(NEW.heading_path, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS rag_chunks_ad_fts
AFTER DELETE ON rag_chunks
BEGIN
    DELETE FROM rag_chunks_fts
    WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS rag_chunk_symbols_ai_fts
AFTER INSERT ON rag_chunk_symbols
BEGIN
    DELETE FROM rag_chunks_fts
    WHERE rowid = (
        SELECT c.rowid
        FROM rag_chunks AS c
        WHERE c.chunk_id = NEW.chunk_id
    );

    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    SELECT
        c.rowid,
        c.chunk_id,
        c.document_id,
        c.project_id,
        c.content,
        COALESCE(c.path, ''),
        trim(
            COALESCE(c.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = c.chunk_id
                ),
                ''
            )
        ),
        COALESCE(c.git_message, ''),
        COALESCE(c.title, ''),
        COALESCE(c.heading_path, '')
    FROM rag_chunks AS c
    WHERE c.chunk_id = NEW.chunk_id;
END;

CREATE TRIGGER IF NOT EXISTS rag_chunk_symbols_ad_fts
AFTER DELETE ON rag_chunk_symbols
BEGIN
    DELETE FROM rag_chunks_fts
    WHERE rowid = (
        SELECT c.rowid
        FROM rag_chunks AS c
        WHERE c.chunk_id = OLD.chunk_id
    );

    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    SELECT
        c.rowid,
        c.chunk_id,
        c.document_id,
        c.project_id,
        c.content,
        COALESCE(c.path, ''),
        trim(
            COALESCE(c.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = c.chunk_id
                ),
                ''
            )
        ),
        COALESCE(c.git_message, ''),
        COALESCE(c.title, ''),
        COALESCE(c.heading_path, '')
    FROM rag_chunks AS c
    WHERE c.chunk_id = OLD.chunk_id;
END;

CREATE TRIGGER IF NOT EXISTS rag_chunk_symbols_au_fts
AFTER UPDATE ON rag_chunk_symbols
BEGIN
    DELETE FROM rag_chunks_fts
    WHERE rowid = (
        SELECT c.rowid
        FROM rag_chunks AS c
        WHERE c.chunk_id = OLD.chunk_id
    );

    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    SELECT
        c.rowid,
        c.chunk_id,
        c.document_id,
        c.project_id,
        c.content,
        COALESCE(c.path, ''),
        trim(
            COALESCE(c.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = c.chunk_id
                ),
                ''
            )
        ),
        COALESCE(c.git_message, ''),
        COALESCE(c.title, ''),
        COALESCE(c.heading_path, '')
    FROM rag_chunks AS c
    WHERE c.chunk_id = OLD.chunk_id;

    DELETE FROM rag_chunks_fts
    WHERE NEW.chunk_id <> OLD.chunk_id
      AND rowid = (
          SELECT c.rowid
          FROM rag_chunks AS c
          WHERE c.chunk_id = NEW.chunk_id
      );

    INSERT INTO rag_chunks_fts (
        rowid,
        chunk_id,
        document_id,
        project_id,
        content,
        path,
        symbol,
        git_message,
        title,
        heading_path
    )
    SELECT
        c.rowid,
        c.chunk_id,
        c.document_id,
        c.project_id,
        c.content,
        COALESCE(c.path, ''),
        trim(
            COALESCE(c.symbol, '')
            || ' '
            || COALESCE(
                (
                    SELECT group_concat(
                        s.name
                        || ' '
                        || s.qualified_name
                        || ' '
                        || COALESCE(s.parent, ''),
                        ' '
                    )
                    FROM rag_chunk_symbols AS s
                    WHERE s.chunk_id = c.chunk_id
                ),
                ''
            )
        ),
        COALESCE(c.git_message, ''),
        COALESCE(c.title, ''),
        COALESCE(c.heading_path, '')
    FROM rag_chunks AS c
    WHERE NEW.chunk_id <> OLD.chunk_id
      AND c.chunk_id = NEW.chunk_id;
END;
"""


_FTS_REBUILD_INSERT_SQL = """
INSERT INTO rag_chunks_fts (
    rowid,
    chunk_id,
    document_id,
    project_id,
    content,
    path,
    symbol,
    git_message,
    title,
    heading_path
)
SELECT
    c.rowid,
    c.chunk_id,
    c.document_id,
    c.project_id,
    c.content,
    COALESCE(c.path, ''),
    trim(
        COALESCE(c.symbol, '')
        || ' '
        || COALESCE(
            (
                SELECT group_concat(
                    s.name
                    || ' '
                    || s.qualified_name
                    || ' '
                    || COALESCE(s.parent, ''),
                    ' '
                )
                FROM rag_chunk_symbols AS s
                WHERE s.chunk_id = c.chunk_id
            ),
            ''
        )
    ),
    COALESCE(c.git_message, ''),
    COALESCE(c.title, ''),
    COALESCE(c.heading_path, '')
FROM rag_chunks AS c
ORDER BY c.rowid
"""


def _require_connection(connection: sqlite3.Connection) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")


def fts5_available(connection: sqlite3.Connection) -> bool:
    """Probe FTS5 support using only a temporary virtual table."""

    _require_connection(connection)
    probe = "__rag_fts5_probe"

    try:
        connection.execute(
            f"DROP TABLE IF EXISTS temp.{probe}"
        )
        connection.execute(
            f"CREATE VIRTUAL TABLE temp.{probe} USING fts5(value)"
        )
        connection.execute(
            f"DROP TABLE temp.{probe}"
        )
        return True
    except sqlite3.OperationalError:
        try:
            connection.execute(
                f"DROP TABLE IF EXISTS temp.{probe}"
            )
        except sqlite3.OperationalError:
            pass
        return False


def fts5_table_exists(connection: sqlite3.Connection) -> bool:
    _require_connection(connection)
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (FTS_TABLE,),
    ).fetchone()
    return bool(
        row
        and row[0]
        and "USING fts5" in str(row[0])
    )


def fts5_trigger_names(
    connection: sqlite3.Connection,
) -> FrozenSet[str]:
    _require_connection(connection)
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'trigger'
          AND name LIKE '%_fts'
        """
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def verify_fts5_integrity(
    connection: sqlite3.Connection,
) -> None:
    _require_connection(connection)

    if not fts5_table_exists(connection):
        raise RagFts5IntegrityError(
            f"missing FTS5 table {FTS_TABLE}"
        )

    triggers = fts5_trigger_names(connection)
    missing = REQUIRED_FTS_TRIGGERS.difference(triggers)
    if missing:
        names = ", ".join(sorted(missing))
        raise RagFts5IntegrityError(
            f"missing FTS5 synchronization triggers: {names}"
        )


def rebuild_fts5(
    connection: sqlite3.Connection,
) -> int:
    """Rebuild the projection from relational RAG chunks and symbols."""

    _require_connection(connection)
    verify_fts5_integrity(connection)

    connection.execute(
        f"DELETE FROM {FTS_TABLE}"
    )
    connection.execute(_FTS_REBUILD_INSERT_SQL)
    connection.commit()

    row = connection.execute(
        f"SELECT count(*) FROM {FTS_TABLE}"
    ).fetchone()
    return int(row[0])


def initialize_fts5(
    connection: sqlite3.Connection,
    *,
    rebuild: bool = True,
) -> int:
    """Create the FTS5 projection explicitly and optionally rebuild it."""

    _require_connection(connection)
    initialize_rag_schema(connection)

    if not fts5_available(connection):
        raise RagFts5UnavailableError(
            "SQLite runtime does not provide FTS5"
        )

    try:
        connection.execute(_FTS_CREATE_SQL)
        connection.executescript(_FTS_TRIGGER_SQL)
    except sqlite3.OperationalError as exc:
        if "fts5" in str(exc).lower():
            raise RagFts5UnavailableError(str(exc)) from exc
        raise

    verify_fts5_integrity(connection)

    if rebuild:
        return rebuild_fts5(connection)

    connection.commit()
    row = connection.execute(
        f"SELECT count(*) FROM {FTS_TABLE}"
    ).fetchone()
    return int(row[0])
