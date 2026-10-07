"""SQLite schema for the lexical RAG index — RAG-005-A.

This module uses only the Python standard library.
Importing it does not open or create any database.
Schema creation happens only through an explicit function call.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import FrozenSet, Union


SCHEMA_VERSION = 1
DEFAULT_DATABASE_FILENAME = "rag_index.sqlite3"

REQUIRED_TABLES: FrozenSet[str] = frozenset({
    "rag_documents",
    "rag_chunks",
    "rag_chunk_symbols",
    "rag_index_state",
})


class RagSchemaVersionError(RuntimeError):
    pass


class RagSchemaIntegrityError(RuntimeError):
    pass


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rag_documents (
    document_id TEXT PRIMARY KEY
        CHECK (length(trim(document_id)) > 0),
    project_id TEXT NOT NULL
        CHECK (length(trim(project_id)) > 0),
    source_type TEXT NOT NULL
        CHECK (
            source_type IN (
                'DOCUMENTATION',
                'CODE',
                'GIT',
                'AUDIT',
                'LOG',
                'EXECUTION',
                'OTHER'
            )
        ),
    content TEXT NOT NULL,
    path TEXT,
    symbol TEXT,
    line_start INTEGER
        CHECK (line_start IS NULL OR line_start >= 1),
    line_end INTEGER
        CHECK (
            line_end IS NULL OR (
                line_start IS NOT NULL
                AND line_end >= line_start
            )
        ),
    git_branch TEXT,
    git_commit TEXT,
    sha256 TEXT
        CHECK (sha256 IS NULL OR length(sha256) = 64),
    indexed_at TEXT,
    source_id TEXT,
    title TEXT,
    heading_path TEXT,
    git_message TEXT
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY
        CHECK (length(trim(chunk_id)) > 0),
    document_id TEXT NOT NULL,
    project_id TEXT NOT NULL
        CHECK (length(trim(project_id)) > 0),
    ordinal INTEGER NOT NULL
        CHECK (ordinal >= 0),
    parent_chunk_id TEXT,
    content TEXT NOT NULL
        CHECK (length(content) > 0),
    source_type TEXT NOT NULL
        CHECK (
            source_type IN (
                'DOCUMENTATION',
                'CODE',
                'GIT',
                'AUDIT',
                'LOG',
                'EXECUTION',
                'OTHER'
            )
        ),
    path TEXT,
    symbol TEXT,
    line_start INTEGER
        CHECK (line_start IS NULL OR line_start >= 1),
    line_end INTEGER
        CHECK (
            line_end IS NULL OR (
                line_start IS NOT NULL
                AND line_end >= line_start
            )
        ),
    git_branch TEXT,
    git_commit TEXT,
    sha256 TEXT
        CHECK (sha256 IS NULL OR length(sha256) = 64),
    indexed_at TEXT,
    source_id TEXT,
    title TEXT,
    heading_path TEXT,
    git_message TEXT,
    chunk_kind TEXT,
    parser_mode TEXT
        CHECK (
            parser_mode IS NULL
            OR parser_mode IN ('STRUCTURAL', 'FALLBACK')
        ),
    FOREIGN KEY (document_id)
        REFERENCES rag_documents(document_id)
        ON DELETE CASCADE,
    FOREIGN KEY (parent_chunk_id)
        REFERENCES rag_chunks(chunk_id)
        ON DELETE SET NULL,
    UNIQUE (document_id, ordinal)
);

CREATE TABLE IF NOT EXISTS rag_chunk_symbols (
    chunk_id TEXT NOT NULL,
    symbol_kind TEXT NOT NULL
        CHECK (
            symbol_kind IN (
                'MODULE',
                'CLASS',
                'FUNCTION',
                'METHOD',
                'CONSTANT',
                'NAMESPACE'
            )
        ),
    name TEXT NOT NULL
        CHECK (length(trim(name)) > 0),
    qualified_name TEXT NOT NULL
        CHECK (length(trim(qualified_name)) > 0),
    parent TEXT,
    line_start INTEGER NOT NULL
        CHECK (line_start >= 1),
    line_end INTEGER NOT NULL
        CHECK (line_end >= line_start),
    FOREIGN KEY (chunk_id)
        REFERENCES rag_chunks(chunk_id)
        ON DELETE CASCADE,
    PRIMARY KEY (
        chunk_id,
        qualified_name,
        symbol_kind,
        line_start,
        line_end
    )
);

CREATE TABLE IF NOT EXISTS rag_index_state (
    project_id TEXT PRIMARY KEY
        CHECK (length(trim(project_id)) > 0),
    state TEXT NOT NULL
        CHECK (
            state IN (
                'UNAVAILABLE',
                'EMPTY',
                'INDEXING',
                'READY',
                'STALE',
                'ERROR'
            )
        ),
    schema_version INTEGER NOT NULL
        CHECK (schema_version = 1),
    source_revision TEXT,
    last_indexed_at TEXT,
    document_count INTEGER NOT NULL DEFAULT 0
        CHECK (document_count >= 0),
    chunk_count INTEGER NOT NULL DEFAULT 0
        CHECK (chunk_count >= 0),
    last_error_type TEXT,
    last_error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_project_source
    ON rag_documents(project_id, source_type);

CREATE INDEX IF NOT EXISTS idx_rag_documents_project_path
    ON rag_documents(project_id, path);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_ordinal
    ON rag_chunks(document_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_project_source
    ON rag_chunks(project_id, source_type);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_project_path
    ON rag_chunks(project_id, path);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_git_commit
    ON rag_chunks(git_commit);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_symbols_name
    ON rag_chunk_symbols(name);

CREATE INDEX IF NOT EXISTS idx_rag_chunk_symbols_qualified
    ON rag_chunk_symbols(qualified_name);
"""


def _require_connection(connection: sqlite3.Connection) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")


def _user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def schema_table_names(
    connection: sqlite3.Connection,
) -> FrozenSet[str]:
    _require_connection(connection)
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def _verify_required_tables(
    connection: sqlite3.Connection,
) -> None:
    present = schema_table_names(connection)
    missing = REQUIRED_TABLES.difference(present)
    if missing:
        names = ", ".join(sorted(missing))
        raise RagSchemaIntegrityError(
            f"RAG schema version {SCHEMA_VERSION} is missing tables: {names}"
        )


def initialize_rag_schema(
    connection: sqlite3.Connection,
) -> int:
    """Create or verify the current schema on an explicit connection."""

    _require_connection(connection)
    connection.execute("PRAGMA foreign_keys = ON")

    version = _user_version(connection)
    if version not in (0, SCHEMA_VERSION):
        raise RagSchemaVersionError(
            f"unsupported RAG schema version {version}; "
            f"expected 0 or {SCHEMA_VERSION}"
        )

    if version == 0:
        connection.executescript(_SCHEMA_SQL)
        connection.execute(
            f"PRAGMA user_version = {SCHEMA_VERSION}"
        )
        connection.commit()

    _verify_required_tables(connection)
    return SCHEMA_VERSION


def connect_rag_index(
    database: Union[str, Path],
) -> sqlite3.Connection:
    """Open an explicitly requested RAG SQLite database and ensure schema v1."""

    value = str(database).strip()
    if not value:
        raise ValueError("database path must be non-empty")

    connection = sqlite3.connect(value)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        initialize_rag_schema(connection)
    except Exception:
        connection.close()
        raise

    return connection
