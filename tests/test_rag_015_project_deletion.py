import hashlib
import tempfile
import unittest
from pathlib import Path

from rag.contracts import SearchQuery, SourceType
from rag.index.fts5 import initialize_fts5
from rag.index.lexical_ranking import search_lexical_ranked
from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
    load_index_manifest,
    save_index_manifest,
)
from rag.index.purge import delete_project_index
from rag.index.qdrant_local import (
    CODE_VECTOR_COLLECTION,
    TEXT_VECTOR_COLLECTION,
    close_qdrant_local,
    ensure_vector_collections,
    open_qdrant_local,
)
from rag.index.sqlite_schema import connect_rag_index
from rag.index.vector_ids import upsert_vector_chunk
from rag.index.vector_namespace import build_project_namespace_filter
from rag.models.code_embedding import CODE_EMBEDDING_DIMENSION
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION


PROJECT_A = "codebridge"
PROJECT_B = "drones"


def basis(dimension, index=0):
    values = [0.0] * dimension
    values[index] = 1.0
    return values


def insert_document_and_chunk(
    connection,
    *,
    project_id,
    suffix,
    source_type,
    content,
    path,
):
    document_id = f"doc-{project_id}-{suffix}"
    chunk_id = f"chunk-{project_id}-{suffix}"

    connection.execute(
        """
        INSERT INTO rag_documents (
            document_id,
            project_id,
            source_type,
            content,
            path,
            sha256,
            indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            project_id,
            source_type,
            content,
            path,
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "2026-10-08T19:00:00-03:00",
        ),
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
            path,
            line_start,
            line_end,
            sha256,
            indexed_at
        ) VALUES (?, ?, ?, 0, ?, ?, ?, 1, 1, ?, ?)
        """,
        (
            chunk_id,
            document_id,
            project_id,
            content,
            source_type,
            path,
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "2026-10-08T19:00:00-03:00",
        ),
    )
    connection.execute(
        """
        INSERT INTO rag_chunk_symbols (
            chunk_id,
            symbol_kind,
            name,
            qualified_name,
            parent,
            line_start,
            line_end
        ) VALUES (?, 'FUNCTION', ?, ?, NULL, 1, 1)
        """,
        (
            chunk_id,
            f"symbol_{suffix}",
            f"symbol_{suffix}",
        ),
    )
    return document_id, chunk_id


def point_payload(document_id, content, source_type, path):
    return {
        "document_id": document_id,
        "content": content,
        "source_type": source_type,
        "path": path,
    }


class Rag015ProjectDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)

        self.source_root = base / "sources"
        self.source_root.mkdir()
        self.source_a = self.source_root / "project-a.txt"
        self.source_b = self.source_root / "project-b.txt"
        self.source_a.write_bytes(b"ORIGINAL PROJECT A SOURCE\n")
        self.source_b.write_bytes(b"ORIGINAL PROJECT B SOURCE\n")
        self.source_a_before = (
            self.source_a.read_bytes(),
            self.source_a.stat().st_mtime_ns,
        )
        self.source_b_before = (
            self.source_b.read_bytes(),
            self.source_b.stat().st_mtime_ns,
        )

        self.sqlite_path = base / "rag.sqlite3"
        self.connection = connect_rag_index(self.sqlite_path)
        self.addCleanup(self.connection.close)

        self.a_text_doc, self.a_text_chunk = insert_document_and_chunk(
            self.connection,
            project_id=PROJECT_A,
            suffix="text",
            source_type=SourceType.DOCUMENTATION.value,
            content="alpha project marker",
            path="docs/a.md",
        )
        self.a_code_doc, self.a_code_chunk = insert_document_and_chunk(
            self.connection,
            project_id=PROJECT_A,
            suffix="code",
            source_type=SourceType.CODE.value,
            content="alpha_code_marker",
            path="src/a.py",
        )
        self.b_text_doc, self.b_text_chunk = insert_document_and_chunk(
            self.connection,
            project_id=PROJECT_B,
            suffix="text",
            source_type=SourceType.DOCUMENTATION.value,
            content="beta project marker",
            path="docs/b.md",
        )
        self.b_code_doc, self.b_code_chunk = insert_document_and_chunk(
            self.connection,
            project_id=PROJECT_B,
            suffix="code",
            source_type=SourceType.CODE.value,
            content="beta_code_marker",
            path="src/b.py",
        )

        for project in (PROJECT_A, PROJECT_B):
            self.connection.execute(
                """
                INSERT INTO rag_index_state (
                    project_id,
                    state,
                    schema_version,
                    document_count,
                    chunk_count
                ) VALUES (?, 'READY', 1, 2, 2)
                """,
                (project,),
            )

        self.connection.commit()
        initialize_fts5(self.connection)

        self.qdrant_path = base / "qdrant"
        self.vector_client = open_qdrant_local(self.qdrant_path)
        self.addCleanup(
            lambda: close_qdrant_local(self.vector_client)
        )
        ensure_vector_collections(self.vector_client)

        for project, text_doc, text_chunk, code_doc, code_chunk, prefix in (
            (
                PROJECT_A,
                self.a_text_doc,
                self.a_text_chunk,
                self.a_code_doc,
                self.a_code_chunk,
                "alpha",
            ),
            (
                PROJECT_B,
                self.b_text_doc,
                self.b_text_chunk,
                self.b_code_doc,
                self.b_code_chunk,
                "beta",
            ),
        ):
            upsert_vector_chunk(
                self.vector_client,
                collection_name=TEXT_VECTOR_COLLECTION,
                project_id=project,
                chunk_id=text_chunk,
                vector=basis(TEXT_EMBEDDING_DIMENSION),
                payload=point_payload(
                    text_doc,
                    f"{prefix} project marker",
                    SourceType.DOCUMENTATION.value,
                    f"docs/{prefix}.md",
                ),
            )
            upsert_vector_chunk(
                self.vector_client,
                collection_name=CODE_VECTOR_COLLECTION,
                project_id=project,
                chunk_id=code_chunk,
                vector=basis(CODE_EMBEDDING_DIMENSION),
                payload=point_payload(
                    code_doc,
                    f"{prefix}_code_marker",
                    SourceType.CODE.value,
                    f"src/{prefix}.py",
                ),
            )

        self.manifest_path = base / "rag-index-manifest.json"
        save_index_manifest(
            self.manifest_path,
            IndexManifest(
                entries=(
                    ManifestEntry(
                        project_id=PROJECT_A,
                        index_kind=ManifestIndexKind.TEXT,
                        path="docs/a.md",
                        size=10,
                        mtime_ns=1,
                        sha256="a" * 64,
                        chunk_ids=(self.a_text_chunk,),
                        model_version="text-v1",
                    ),
                    ManifestEntry(
                        project_id=PROJECT_A,
                        index_kind=ManifestIndexKind.CODE,
                        path="src/a.py",
                        size=10,
                        mtime_ns=1,
                        sha256="b" * 64,
                        chunk_ids=(self.a_code_chunk,),
                        model_version="code-v1",
                    ),
                    ManifestEntry(
                        project_id=PROJECT_B,
                        index_kind=ManifestIndexKind.TEXT,
                        path="docs/b.md",
                        size=10,
                        mtime_ns=1,
                        sha256="c" * 64,
                        chunk_ids=(self.b_text_chunk,),
                        model_version="text-v1",
                    ),
                    ManifestEntry(
                        project_id=PROJECT_B,
                        index_kind=ManifestIndexKind.CODE,
                        path="src/b.py",
                        size=10,
                        mtime_ns=1,
                        sha256="d" * 64,
                        chunk_ids=(self.b_code_chunk,),
                        model_version="code-v1",
                    ),
                )
            ),
        )

    def vector_count(self, collection, project_id):
        result = self.vector_client.count(
            collection_name=collection,
            count_filter=build_project_namespace_filter(project_id),
            exact=True,
        )
        return int(result.count)

    def assert_sources_untouched(self):
        self.assertTrue(self.source_a.is_file())
        self.assertTrue(self.source_b.is_file())
        self.assertEqual(
            (self.source_a.read_bytes(), self.source_a.stat().st_mtime_ns),
            self.source_a_before,
        )
        self.assertEqual(
            (self.source_b.read_bytes(), self.source_b.stat().st_mtime_ns),
            self.source_b_before,
        )

    def test_delete_project_index_removes_only_project_a_derived_data(self):
        result = delete_project_index(
            self.connection,
            self.vector_client,
            PROJECT_A,
            manifest_path=self.manifest_path,
        )

        self.assertEqual(result.project_id, PROJECT_A)
        self.assertEqual(result.sqlite_documents_deleted, 2)
        self.assertEqual(result.sqlite_chunks_deleted, 2)
        self.assertEqual(result.sqlite_symbols_deleted, 2)
        self.assertEqual(result.sqlite_state_deleted, 1)
        self.assertEqual(result.text_vectors_deleted, 1)
        self.assertEqual(result.code_vectors_deleted, 1)
        self.assertEqual(result.manifest_entries_deleted, 2)

        for table in ("rag_documents", "rag_chunks", "rag_index_state"):
            count_a = self.connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
                (PROJECT_A,),
            ).fetchone()[0]
            count_b = self.connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
                (PROJECT_B,),
            ).fetchone()[0]
            self.assertEqual(count_a, 0)
            self.assertGreater(count_b, 0)

        self.assertEqual(
            self.vector_count(TEXT_VECTOR_COLLECTION, PROJECT_A),
            0,
        )
        self.assertEqual(
            self.vector_count(CODE_VECTOR_COLLECTION, PROJECT_A),
            0,
        )
        self.assertEqual(
            self.vector_count(TEXT_VECTOR_COLLECTION, PROJECT_B),
            1,
        )
        self.assertEqual(
            self.vector_count(CODE_VECTOR_COLLECTION, PROJECT_B),
            1,
        )

        manifest = load_index_manifest(self.manifest_path)
        self.assertFalse(
            any(entry.project_id == PROJECT_A for entry in manifest.entries)
        )
        self.assertEqual(
            sum(entry.project_id == PROJECT_B for entry in manifest.entries),
            2,
        )

        a_results = search_lexical_ranked(
            self.connection,
            SearchQuery(
                query="alpha project marker",
                project_id=PROJECT_A,
                top_k=10,
            ),
        )
        b_results = search_lexical_ranked(
            self.connection,
            SearchQuery(
                query="beta project marker",
                project_id=PROJECT_B,
                top_k=10,
            ),
        )
        self.assertEqual(a_results, ())
        self.assertTrue(b_results)

        self.assert_sources_untouched()

    def test_deletion_is_idempotent_and_sources_remain_untouched(self):
        delete_project_index(
            self.connection,
            self.vector_client,
            PROJECT_A,
            manifest_path=self.manifest_path,
        )
        second = delete_project_index(
            self.connection,
            self.vector_client,
            PROJECT_A,
            manifest_path=self.manifest_path,
        )

        self.assertEqual(second.sqlite_documents_deleted, 0)
        self.assertEqual(second.sqlite_chunks_deleted, 0)
        self.assertEqual(second.sqlite_symbols_deleted, 0)
        self.assertEqual(second.sqlite_state_deleted, 0)
        self.assertEqual(second.text_vectors_deleted, 0)
        self.assertEqual(second.code_vectors_deleted, 0)
        self.assertEqual(second.manifest_entries_deleted, 0)
        self.assert_sources_untouched()

    def test_shared_qdrant_collections_are_not_dropped(self):
        delete_project_index(
            self.connection,
            self.vector_client,
            PROJECT_A,
        )

        self.assertTrue(
            self.vector_client.collection_exists(TEXT_VECTOR_COLLECTION)
        )
        self.assertTrue(
            self.vector_client.collection_exists(CODE_VECTOR_COLLECTION)
        )
        self.assertEqual(
            self.vector_count(TEXT_VECTOR_COLLECTION, PROJECT_B),
            1,
        )
        self.assertEqual(
            self.vector_count(CODE_VECTOR_COLLECTION, PROJECT_B),
            1,
        )

    def test_manifest_remove_project_preserves_other_namespace(self):
        manifest = load_index_manifest(self.manifest_path)

        updated = manifest.remove_project(PROJECT_A)

        self.assertFalse(
            any(entry.project_id == PROJECT_A for entry in updated.entries)
        )
        self.assertEqual(
            sum(entry.project_id == PROJECT_B for entry in updated.entries),
            2,
        )

    def test_invalid_namespace_is_rejected_before_deletion(self):
        with self.assertRaises(ValueError):
            delete_project_index(
                self.connection,
                self.vector_client,
                "CodeBridge",
                manifest_path=self.manifest_path,
            )

        self.assertEqual(
            self.vector_count(TEXT_VECTOR_COLLECTION, PROJECT_A),
            1,
        )
        self.assert_sources_untouched()


if __name__ == "__main__":
    unittest.main()
