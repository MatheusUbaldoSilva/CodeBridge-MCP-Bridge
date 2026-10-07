"""Storage backends for the CodeBridge RAG layer."""

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
    "DEFAULT_DATABASE_FILENAME",
    "REQUIRED_TABLES",
    "SCHEMA_VERSION",
    "RagSchemaIntegrityError",
    "RagSchemaVersionError",
    "connect_rag_index",
    "initialize_rag_schema",
    "schema_table_names",
]
