import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.index.manifest import (
    IndexManifest,
    ManifestEntry,
    ManifestIndexKind,
    save_index_manifest,
)
from rag.index.sqlite_schema import connect_rag_index
import rag.runtime.status as rag_status


class RagStatusSnapshotTests(unittest.TestCase):
    def test_status_uses_one_explicitly_pinned_generation(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "generations" / "v1_delta_fixture"
            path.mkdir(parents=True)
            (path / "qdrant").mkdir()
            db_path = path / "rag_index.sqlite3"
            database = connect_rag_index(db_path)
            try:
                database.execute(
                    "INSERT INTO rag_index_state "
                    "(project_id,state,schema_version,document_count,chunk_count) "
                    "VALUES ('codebridge','READY',1,211,8766)"
                )
                database.commit()
            finally:
                database.close()
            manifest_path = path / "rag-index-manifest.json"
            save_index_manifest(
                manifest_path, IndexManifest(entries=(
                    ManifestEntry(
                        project_id="codebridge",
                        index_kind=ManifestIndexKind.CODE,
                        path="rag/runtime/live_integrity.py",
                        size=12, mtime_ns=1,
                        sha256="a" * 64, chunk_ids=("c1",),
                        model_version="code-v1",
                    ),
                ))
            )
            pinned = SimpleNamespace(
                generation="v1_delta_fixture",
                sqlite=db_path, manifest=manifest_path, qdrant=path / "qdrant",
            )
            with patch.object(rag_status, "_probe_model_process",
                              return_value=(False, "UNLOADED")):
                report = rag_status.build_rag_status(
                    _generation_paths=pinned,
                ).to_dict()
            self.assertEqual(report["index"]["generation"], "v1_delta_fixture")
            self.assertEqual(report["index"]["state"], "READY")
            self.assertEqual(report["projects"][0]["document_count"], 211)
            self.assertEqual(report["projects"][0]["chunk_count"], 8766)
            self.assertEqual(report["index"]["manifest_path"], str(manifest_path))

    def test_empty_state_reports_empty_without_creating_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            with patch.object(
                rag_status,
                "_probe_model_process",
                return_value=(False, "UNLOADED"),
            ):
                status = rag_status.build_rag_status(
                    local_app_data=root
                ).to_dict()

            self.assertEqual(status["index"]["state"], "EMPTY")
            self.assertFalse(status["index"]["manifest_exists"])
            self.assertFalse(status["index"]["sqlite_exists"])
            self.assertEqual(status["projects"], [])
            self.assertIsNone(status["last_indexed_at"])
            self.assertEqual(
                status["backend"]["vector"],
                "QDRANT_LOCAL",
            )
            self.assertEqual(
                status["models"]["text"]["runtime_state"],
                "UNLOADED",
            )
            self.assertEqual(
                status["models"]["code"]["runtime_state"],
                "UNLOADED",
            )
            self.assertFalse(
                rag_status.resolve_rag_manifest_path(
                    local_app_data=root
                ).exists()
            )
            self.assertFalse(
                rag_status.resolve_rag_sqlite_path(
                    local_app_data=root
                ).exists()
            )

    def test_manifest_projects_and_model_versions_are_exposed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = rag_status.resolve_rag_manifest_path(
                local_app_data=root
            )
            manifest = IndexManifest(
                entries=(
                    ManifestEntry(
                        project_id="codebridge",
                        index_kind=ManifestIndexKind.TEXT,
                        path="docs/readme.md",
                        size=10,
                        mtime_ns=1,
                        sha256="a" * 64,
                        chunk_ids=("t1",),
                        model_version="text-v1",
                    ),
                    ManifestEntry(
                        project_id="codebridge",
                        index_kind=ManifestIndexKind.CODE,
                        path="src/main.py",
                        size=20,
                        mtime_ns=2,
                        sha256="b" * 64,
                        chunk_ids=("c1",),
                        model_version="code-v1",
                    ),
                    ManifestEntry(
                        project_id="drones",
                        index_kind=ManifestIndexKind.TEXT,
                        path="docs/a.md",
                        size=30,
                        mtime_ns=3,
                        sha256="c" * 64,
                        chunk_ids=("d1",),
                        model_version="text-v1",
                    ),
                )
            )
            save_index_manifest(manifest_path, manifest)

            with patch.object(
                rag_status,
                "_probe_model_process",
                return_value=(False, "UNLOADED"),
            ):
                status = rag_status.build_rag_status(
                    local_app_data=root
                ).to_dict()

            self.assertEqual(status["index"]["state"], "STALE")
            self.assertEqual(status["index"]["manifest_entries"], 3)
            by_id = {
                item["project_id"]: item
                for item in status["projects"]
            }
            self.assertEqual(
                by_id["codebridge"]["text_entries"],
                1,
            )
            self.assertEqual(
                by_id["codebridge"]["code_entries"],
                1,
            )
            self.assertEqual(
                by_id["codebridge"]["text_model_versions"],
                ["text-v1"],
            )
            self.assertEqual(
                by_id["codebridge"]["code_model_versions"],
                ["code-v1"],
            )
            self.assertEqual(
                by_id["drones"]["manifest_entries"],
                1,
            )

    def test_sqlite_index_state_exposes_last_indexing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            database = rag_status.resolve_rag_sqlite_path(
                local_app_data=root
            )
            database.parent.mkdir(parents=True)
            connection = connect_rag_index(database)
            try:
                connection.execute(
                    """
                    INSERT INTO rag_index_state (
                        project_id,
                        state,
                        schema_version,
                        source_revision,
                        last_indexed_at,
                        document_count,
                        chunk_count
                    ) VALUES (?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        "codebridge",
                        "READY",
                        "abc123",
                        "2026-10-07T22:00:00+00:00",
                        4,
                        12,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(
                rag_status,
                "_probe_model_process",
                return_value=(False, "UNLOADED"),
            ):
                status = rag_status.build_rag_status(
                    local_app_data=root
                ).to_dict()

            self.assertEqual(status["index"]["state"], "STALE")
            self.assertEqual(
                status["last_indexed_at"],
                "2026-10-07T22:00:00+00:00",
            )
            project = status["projects"][0]
            self.assertEqual(project["project_id"], "codebridge")
            self.assertEqual(project["document_count"], 4)
            self.assertEqual(project["chunk_count"], 12)
            self.assertEqual(project["index_state"], "READY")

    def test_error_project_promotes_overall_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            database = rag_status.resolve_rag_sqlite_path(
                local_app_data=root
            )
            database.parent.mkdir(parents=True)
            connection = connect_rag_index(database)
            try:
                connection.execute(
                    """
                    INSERT INTO rag_index_state (
                        project_id,
                        state,
                        schema_version,
                        document_count,
                        chunk_count,
                        last_error_type,
                        last_error_message
                    ) VALUES ('codebridge', 'ERROR', 1, 0, 0, 'X', 'boom')
                    """
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(
                rag_status,
                "_probe_model_process",
                return_value=(None, "UNKNOWN"),
            ):
                status = rag_status.build_rag_status(
                    local_app_data=root
                ).to_dict()

            self.assertEqual(status["index"]["state"], "ERROR")
            self.assertEqual(
                status["projects"][0]["last_error_type"],
                "X",
            )
            self.assertEqual(
                status["models"]["text"]["runtime_state"],
                "UNKNOWN",
            )


if __name__ == "__main__":
    unittest.main()
