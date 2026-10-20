"""Real installed Jina offline worker E2E with an isolated synthetic Git source."""
from pathlib import Path
from unittest.mock import patch
from test_incremental_job_queue import DurableQueueTests
from rag.runtime.incremental_offline_worker import process_offline_job_once
from rag.runtime.incremental_job_queue import inspect_job, inspect_job_queue
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.artifact_install import resolve_selected_model_path

class InstalledWorkerE2ETests(DurableQueueTests):
    def test_real_code_staging_receipt_without_publication(self):
        import sqlite3
        import unittest
        exe=Path(r"C:\llama\llama-server.exe")
        if not (exe.is_file() and resolve_selected_code_model_path().is_file()):
            self.skipTest("installed local Jina Code model unavailable")
        self.enqueue(queue_enabled=True,now_epoch=140)
        scratch=Path(self.temp.name)/"isolated-runtime"
        scratch.mkdir()
        fake_sqlite=scratch/"rag_index.sqlite3"
        from rag.runtime import production_index
        with patch.object(production_index,"resolve_rag_sqlite_path",return_value=fake_sqlite):
            result=process_offline_job_once(
                self.db,self.root,approved_paths=("sample.py",),
                queue_enabled=True,worker_enabled=True)
        self.assertEqual(result["state"],"STAGED_OFFLINE_VALIDATED",result)
        self.assertTrue(result["acknowledged"])
        self.assertFalse(result["active_index_updated"])
        detail=inspect_job(self.db,result["job_id"])
        self.assertTrue(detail["staged_offline"])
        self.assertGreater(detail["validated_counts"]["vectors"],0)
        self.assertEqual(inspect_job_queue(self.db)["by_state"],{"STAGED_OFFLINE_VALIDATED":1})
        self.assertFalse(fake_sqlite.exists())
        from contextlib import closing
        from rag.index.manifest import load_index_manifest, ManifestIndexKind
        from rag.runtime.status import resolve_rag_manifest_path
        with closing(sqlite3.connect(self.db)) as db:
            staged_path = Path(db.execute(
                "SELECT staging_path FROM staging_receipts").fetchone()[0])
        self.assertTrue(staged_path.is_relative_to(scratch / "staging"))
        actual = load_index_manifest(staged_path / "rag-index-manifest.json")
        public = load_index_manifest(resolve_rag_manifest_path())
        expected_versions = {
            x.model_version for x in public.entries
            if x.project_id == "codebridge" and x.index_kind == ManifestIndexKind.CODE
        }
        self.assertEqual(len(expected_versions), 1)
        self.assertEqual(
            {x.model_version for x in actual.entries}, expected_versions)
