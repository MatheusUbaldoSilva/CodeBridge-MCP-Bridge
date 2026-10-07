"""Storage backends for the CodeBridge RAG layer."""

from .fts5 import (
    FTS_INDEXED_FIELDS,
    FTS_LAYOUT_VERSION,
    FTS_METADATA_FIELDS,
    FTS_TABLE,
    REQUIRED_FTS_TRIGGERS,
    RagFts5IntegrityError,
    RagFts5UnavailableError,
    fts5_available,
    fts5_table_exists,
    fts5_trigger_names,
    initialize_fts5,
    rebuild_fts5,
    verify_fts5_integrity,
)
from .lexical_search import (
    LexicalSearchHit,
    RagLexicalQueryError,
    search_lexical,
)
from .sqlite_schema import (
    DEFAULT_DATABASE_FILENAME,
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    RagSchemaIntegrityError,
    RagSchemaVersionError,
    connect_rag_index,
    initialize_rag_schema,
    schema_table_names,
)

__all__ = [
    "FTS_INDEXED_FIELDS",
    "FTS_LAYOUT_VERSION",
    "FTS_METADATA_FIELDS",
    "FTS_TABLE",
    "REQUIRED_FTS_TRIGGERS",
    "RagFts5IntegrityError",
    "RagFts5UnavailableError",
    "fts5_available",
    "fts5_table_exists",
    "fts5_trigger_names",
    "initialize_fts5",
    "rebuild_fts5",
    "verify_fts5_integrity",
    "LexicalSearchHit",
    "RagLexicalQueryError",
    "search_lexical",
    "DEFAULT_DATABASE_FILENAME",
    "REQUIRED_TABLES",
    "SCHEMA_VERSION",
    "RagSchemaIntegrityError",
    "RagSchemaVersionError",
    "connect_rag_index",
    "initialize_rag_schema",
    "schema_table_names",
]
