import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.index.sqlite_schema import (
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    RagSchemaIntegrityError,
    RagSchemaVersionError,
    connect_rag_index,
    initialize_rag_schema,
    schema_table_names,
)


class RagSqliteSchemaTests(unittest.TestCase):
    def test_schema_initializes_in_memory_with_version_one(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)

        version = initialize_rag_schema(connection)

        self.assertEqual(version, 1)
        self.assertEqual(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0],
            SCHEMA_VERSION,
        )
        self.assertEqual(
            schema_table_names(connection),
            REQUIRED_TABLES,
        )

    def test_file_backed_database_is_created_only_by_explicit_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "rag.sqlite3"
            self.assertFalse(database.exists())

            connection = connect_rag_index(database)
            try:
                self.assertTrue(database.exists())
                self.assertEqual(
                    schema_table_names(connection),
                    REQUIRED_TABLES,
                )
            finally:
                connection.close()

    def test_import_does_not_create_default_database_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            expected = (
                Path(temp_dir)
                / "rag_index.sqlite3"
            )
            self.assertFalse(expected.exists())

            import rag.index.sqlite_schema as module
            importlib.reload(module)

            self.assertFalse(expected.exists())

    def test_foreign_keys_are_enabled_by_connection_helper(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        self.assertEqual(enabled, 1)

    def test_document_chunk_and_symbol_relations_cascade(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES (?, ?, ?, ?)
            """,
            ("doc-1", "project", "CODE", "source"),
        )
        connection.execute(
            """
            INSERT INTO rag_chunks (
                chunk_id,
                document_id,
                project_id,
                ordinal,
                content,
                source_type,
                line_start,
                line_end
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "chunk-1",
                "doc-1",
                "project",
                0,
                "def run():\n    pass",
                "CODE",
                1,
                2,
            ),
        )
        connection.execute(
            """
            INSERT INTO rag_chunk_symbols (
                chunk_id,
                symbol_kind,
                name,
                qualified_name,
                line_start,
                line_end
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "chunk-1",
                "FUNCTION",
                "run",
                "module.run",
                1,
                2,
            ),
        )
        connection.commit()

        connection.execute(
            "DELETE FROM rag_documents WHERE document_id = ?",
            ("doc-1",),
        )
        connection.commit()

        self.assertEqual(
            connection.execute(
                "SELECT count(*) FROM rag_chunks"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            connection.execute(
                "SELECT count(*) FROM rag_chunk_symbols"
            ).fetchone()[0],
            0,
        )

    def test_duplicate_document_ordinal_is_rejected(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES ('doc', 'p', 'CODE', 'x')
            """
        )
        connection.execute(
            """
            INSERT INTO rag_chunks (
                chunk_id,
                document_id,
                project_id,
                ordinal,
                content,
                source_type
            ) VALUES ('a', 'doc', 'p', 0, 'x', 'CODE')
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rag_chunks (
                    chunk_id,
                    document_id,
                    project_id,
                    ordinal,
                    content,
                    source_type
                ) VALUES ('b', 'doc', 'p', 0, 'y', 'CODE')
                """
            )

    def test_invalid_line_range_is_rejected(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES ('doc', 'p', 'CODE', 'x')
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rag_chunks (
                    chunk_id,
                    document_id,
                    project_id,
                    ordinal,
                    content,
                    source_type,
                    line_start,
                    line_end
                ) VALUES (
                    'bad',
                    'doc',
                    'p',
                    0,
                    'x',
                    'CODE',
                    3,
                    2
                )
                """
            )

    def test_invalid_source_type_is_rejected(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rag_documents (
                    document_id,
                    project_id,
                    source_type,
                    content
                ) VALUES ('doc', 'p', 'INVALID', 'x')
                """
            )

    def test_invalid_parser_mode_is_rejected(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        connection.execute(
            """
            INSERT INTO rag_documents (
                document_id,
                project_id,
                source_type,
                content
            ) VALUES ('doc', 'p', 'CODE', 'x')
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rag_chunks (
                    chunk_id,
                    document_id,
                    project_id,
                    ordinal,
                    content,
                    source_type,
                    parser_mode
                ) VALUES (
                    'chunk',
                    'doc',
                    'p',
                    0,
                    'x',
                    'CODE',
                    'MAGIC'
                )
                """
            )

    def test_no_fts_virtual_table_exists_in_005_a(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        rows = connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        rendered = "\n".join(
            f"{name}: {sql or ''}"
            for name, sql in rows
        ).lower()

        self.assertNotIn("virtual table", rendered)
        self.assertNotIn("fts5", rendered)

    def test_no_embedding_schema_is_present(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        rows = connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index')
            """
        ).fetchall()

        rendered = "\n".join(
            f"{name}: {sql or ''}"
            for name, sql in rows
        ).lower()

        self.assertNotIn("embedding", rendered)
        self.assertNotIn("vector", rendered)

    def test_schema_contains_future_lexical_fields_without_fts(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(rag_chunks)"
            ).fetchall()
        }

        self.assertTrue(
            {
                "content",
                "path",
                "symbol",
                "git_message",
                "title",
                "heading_path",
            }.issubset(columns)
        )

    def test_index_state_uses_contract_states(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        for state in (
            "UNAVAILABLE",
            "EMPTY",
            "INDEXING",
            "READY",
            "STALE",
            "ERROR",
        ):
            with self.subTest(state=state):
                connection.execute(
                    """
                    INSERT OR REPLACE INTO rag_index_state (
                        project_id,
                        state,
                        schema_version
                    ) VALUES (?, ?, ?)
                    """,
                    (f"p-{state}", state, SCHEMA_VERSION),
                )

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rag_index_state (
                    project_id,
                    state,
                    schema_version
                ) VALUES ('bad', 'UNKNOWN', 1)
                """
            )

    def test_initialization_is_idempotent(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)

        self.assertEqual(
            initialize_rag_schema(connection),
            SCHEMA_VERSION,
        )
        self.assertEqual(
            initialize_rag_schema(connection),
            SCHEMA_VERSION,
        )
        self.assertEqual(
            schema_table_names(connection),
            REQUIRED_TABLES,
        )

    def test_unknown_schema_version_is_rejected(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("PRAGMA user_version = 99")

        with self.assertRaises(RagSchemaVersionError):
            initialize_rag_schema(connection)

        self.assertEqual(
            schema_table_names(connection),
            frozenset(),
        )

    def test_version_one_with_missing_table_is_rejected(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("PRAGMA user_version = 1")
        connection.execute(
            "CREATE TABLE rag_documents (document_id TEXT)"
        )

        with self.assertRaises(RagSchemaIntegrityError):
            initialize_rag_schema(connection)

    def test_standard_btree_indexes_exist(self):
        connection = connect_rag_index(":memory:")
        self.addCleanup(connection.close)

        indexes = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND name NOT LIKE 'sqlite_autoindex_%'
                """
            ).fetchall()
        }

        self.assertTrue(
            {
                "idx_rag_documents_project_source",
                "idx_rag_documents_project_path",
                "idx_rag_chunks_document_ordinal",
                "idx_rag_chunks_project_source",
                "idx_rag_chunks_project_path",
                "idx_rag_chunks_git_commit",
                "idx_rag_chunk_symbols_name",
                "idx_rag_chunk_symbols_qualified",
            }.issubset(indexes)
        )


if __name__ == "__main__":
    unittest.main()
