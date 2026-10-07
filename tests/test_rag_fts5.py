import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.index.fts5 import (
    FTS_INDEXED_FIELDS,
    FTS_METADATA_FIELDS,
    FTS_TABLE,
    REQUIRED_FTS_TRIGGERS,
    fts5_available,
    fts5_table_exists,
    fts5_trigger_names,
    initialize_fts5,
    rebuild_fts5,
    verify_fts5_integrity,
)
from rag.index.sqlite_schema import (
    SCHEMA_VERSION,
    connect_rag_index,
)


def insert_document(connection, document_id="doc-1"):
    connection.execute(
        """
        INSERT INTO rag_documents (
            document_id,
            project_id,
            source_type,
            content
        ) VALUES (?, 'project', 'CODE', 'source')
        """,
        (document_id,),
    )


def insert_chunk(
    connection,
    *,
    chunk_id="chunk-1",
    document_id="doc-1",
    content="AlphaContentMarker",
    path="src/alpha_module.py",
    symbol="AlphaSymbol",
    git_message="fix AlphaGitMarker",
    title="Alpha Title Marker",
    heading_path="Alpha Heading Marker",
):
    connection.execute(
        """
        INSERT INTO rag_chunks (
            chunk_id,
            document_id,
            project_id,
            ordinal,
            content,
            source_type,
            path,
            symbol,
            git_message,
            title,
            heading_path
        ) VALUES (?, ?, 'project', 0, ?, 'CODE', ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            document_id,
            content,
            path,
            symbol,
            git_message,
            title,
            heading_path,
        ),
    )


def count_match(connection, query):
    return connection.execute(
        f"""
        SELECT count(*)
        FROM {FTS_TABLE}
        WHERE {FTS_TABLE} MATCH ?
        """,
        (query,),
    ).fetchone()[0]


class RagFts5Tests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_rag_index(":memory:")
        self.addCleanup(self.connection.close)
        if not fts5_available(self.connection):
            self.skipTest("SQLite runtime does not provide FTS5")

    def test_fts_is_explicit_not_created_by_base_schema(self):
        self.assertFalse(
            fts5_table_exists(self.connection)
        )
        self.assertEqual(
            self.connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0],
            SCHEMA_VERSION,
        )

    def test_initialize_creates_fts_table_and_all_sync_triggers(self):
        initialize_fts5(self.connection)

        self.assertTrue(
            fts5_table_exists(self.connection)
        )
        self.assertEqual(
            fts5_trigger_names(self.connection),
            REQUIRED_FTS_TRIGGERS,
        )
        verify_fts5_integrity(self.connection)

    def test_layout_indexes_exact_handoff_fields(self):
        self.assertEqual(
            FTS_INDEXED_FIELDS,
            frozenset({
                "content",
                "path",
                "symbol",
                "git_message",
                "title",
                "heading_path",
            }),
        )
        self.assertEqual(
            FTS_METADATA_FIELDS,
            frozenset({
                "chunk_id",
                "document_id",
                "project_id",
            }),
        )

    def test_existing_chunks_are_backfilled_on_initialization(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        self.connection.commit()

        rows = initialize_fts5(self.connection)

        self.assertEqual(rows, 1)
        self.assertEqual(
            self.connection.execute(
                f"SELECT chunk_id FROM {FTS_TABLE}"
            ).fetchall(),
            [("chunk-1",)],
        )

    def test_content_is_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "content:AlphaContentMarker",
            ),
            1,
        )

    def test_path_is_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "path:alpha_module",
            ),
            1,
        )

    def test_chunk_symbol_field_is_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:AlphaSymbol",
            ),
            1,
        )

    def test_symbol_table_names_and_qualified_names_are_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        self.connection.execute(
            """
            INSERT INTO rag_chunk_symbols (
                chunk_id,
                symbol_kind,
                name,
                qualified_name,
                parent,
                line_start,
                line_end
            ) VALUES (
                'chunk-1',
                'METHOD',
                'RunWorker',
                'module.Worker.RunWorker',
                'module.Worker',
                1,
                2
            )
            """
        )
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:RunWorker",
            ),
            1,
        )
        self.assertEqual(
            count_match(
                self.connection,
                "symbol:Worker",
            ),
            1,
        )

    def test_git_message_is_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "git_message:AlphaGitMarker",
            ),
            1,
        )

    def test_title_and_heading_are_indexed(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "title:Alpha",
            ),
            1,
        )
        self.assertEqual(
            count_match(
                self.connection,
                "heading_path:Heading",
            ),
            1,
        )

    def test_new_chunk_is_synchronized_by_trigger(self):
        initialize_fts5(self.connection)
        insert_document(self.connection)
        insert_chunk(self.connection)
        self.connection.commit()

        self.assertEqual(
            count_match(
                self.connection,
                "content:AlphaContentMarker",
            ),
            1,
        )

    def test_chunk_update_refreshes_fts_projection(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.connection.execute(
            """
            UPDATE rag_chunks
            SET content = 'BetaContentMarker'
            WHERE chunk_id = 'chunk-1'
            """
        )
        self.connection.commit()

        self.assertEqual(
            count_match(
                self.connection,
                "content:AlphaContentMarker",
            ),
            0,
        )
        self.assertEqual(
            count_match(
                self.connection,
                "content:BetaContentMarker",
            ),
            1,
        )

    def test_symbol_insert_refreshes_fts_projection(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:LateSymbol",
            ),
            0,
        )

        self.connection.execute(
            """
            INSERT INTO rag_chunk_symbols (
                chunk_id,
                symbol_kind,
                name,
                qualified_name,
                line_start,
                line_end
            ) VALUES (
                'chunk-1',
                'FUNCTION',
                'LateSymbol',
                'module.LateSymbol',
                1,
                1
            )
            """
        )
        self.connection.commit()

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:LateSymbol",
            ),
            1,
        )

    def test_symbol_delete_refreshes_fts_projection(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        self.connection.execute(
            """
            INSERT INTO rag_chunk_symbols (
                chunk_id,
                symbol_kind,
                name,
                qualified_name,
                line_start,
                line_end
            ) VALUES (
                'chunk-1',
                'FUNCTION',
                'TransientSymbol',
                'module.TransientSymbol',
                1,
                1
            )
            """
        )
        initialize_fts5(self.connection)

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:TransientSymbol",
            ),
            1,
        )

        self.connection.execute(
            """
            DELETE FROM rag_chunk_symbols
            WHERE chunk_id = 'chunk-1'
              AND name = 'TransientSymbol'
            """
        )
        self.connection.commit()

        self.assertEqual(
            count_match(
                self.connection,
                "symbol:TransientSymbol",
            ),
            0,
        )

    def test_document_delete_cascade_removes_fts_row(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.connection.execute(
            """
            DELETE FROM rag_documents
            WHERE document_id = 'doc-1'
            """
        )
        self.connection.commit()

        self.assertEqual(
            self.connection.execute(
                f"SELECT count(*) FROM {FTS_TABLE}"
            ).fetchone()[0],
            0,
        )

    def test_rebuild_repairs_projection_from_relational_tables(self):
        insert_document(self.connection)
        insert_chunk(self.connection)
        initialize_fts5(self.connection)

        self.connection.execute(
            f"DELETE FROM {FTS_TABLE}"
        )
        self.connection.commit()

        self.assertEqual(
            self.connection.execute(
                f"SELECT count(*) FROM {FTS_TABLE}"
            ).fetchone()[0],
            0,
        )

        rows = rebuild_fts5(self.connection)

        self.assertEqual(rows, 1)
        self.assertEqual(
            count_match(
                self.connection,
                "content:AlphaContentMarker",
            ),
            1,
        )

    def test_initialization_is_idempotent(self):
        insert_document(self.connection)
        insert_chunk(self.connection)

        self.assertEqual(
            initialize_fts5(self.connection),
            1,
        )
        self.assertEqual(
            initialize_fts5(self.connection),
            1,
        )
        self.assertEqual(
            self.connection.execute(
                f"SELECT count(*) FROM {FTS_TABLE}"
            ).fetchone()[0],
            1,
        )

    def test_fts_does_not_change_relational_schema_version(self):
        initialize_fts5(self.connection)

        self.assertEqual(
            self.connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0],
            1,
        )

    def test_no_embedding_or_vector_storage_is_added(self):
        initialize_fts5(self.connection)

        rows = self.connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'trigger')
            """
        ).fetchall()

        rendered = "\n".join(
            f"{name}: {sql or ''}"
            for name, sql in rows
        ).lower()

        self.assertNotIn("embedding", rendered)
        self.assertNotIn("vector", rendered)

    def test_no_public_search_or_ranking_api_is_implemented_here(self):
        import rag.index.fts5 as module

        self.assertFalse(
            hasattr(module, "search_lexical")
        )
        self.assertFalse(
            hasattr(module, "rank_lexical")
        )
        self.assertNotIn(
            "bm25(",
            Path(module.__file__).read_text(
                encoding="utf-8"
            ).lower(),
        )


if __name__ == "__main__":
    unittest.main()
