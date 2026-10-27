"""RAG-AUTO-05-E guarded queue-bound import adapter tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from rag.runtime.auto_index_incremental_adapter import import_into_approved_auto_stage

MODULE="rag.runtime.auto_index_incremental_adapter."


class QueueBoundImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name)
        (self.stage/"qdrant").mkdir()
        (self.stage/"rag_index.sqlite3").write_bytes(b"lab")
        self.job={"approved":True,"state":"QUEUED","project_id":"canary"}
        self.receipt={"project_id":"canary"}

    def run_import(self,job=None):
        with (
            patch(MODULE+"get_job",return_value=self.job if job is None else job),
            patch(MODULE+"stage_directory",return_value=self.stage),
            patch(MODULE+"verify_candidate_stage_rows",return_value={"matched_rows":1}),
            patch(MODULE+"open_qdrant_local",return_value=Mock()) as opened,
            patch(MODULE+"close_qdrant_local") as closed,
            patch(MODULE+"execute_isolated_reuse_batch",
                  return_value={"vectors_written":1}) as importer,
        ):
            result=import_into_approved_auto_stage(
                Path("unused"),"a"*32,self.receipt,{},{"TEXT":[],"CODE":[]},
                operator_approved=True)
        return result,opened,closed,importer

    def test_queue_bound_stage_writes_and_closes_client(self):
        result,opened,closed,importer=self.run_import()
        self.assertEqual(result["vectors_written"],1)
        opened.assert_called_once_with(self.stage/"qdrant")
        closed.assert_called_once()
        importer.assert_called_once()

    def test_unapproved_and_public_jobs_denied(self):
        for job in ({**self.job,"approved":False},
                    {**self.job,"state":"DRAFT"},
                    {**self.job,"project_id":"codebridge"}):
            with patch(MODULE+"get_job",return_value=job), self.assertRaises(PermissionError):
                import_into_approved_auto_stage(
                    Path("unused"),"a"*32,self.receipt,{},{"TEXT":[],"CODE":[]},
                    operator_approved=True)

    def test_wrong_project_denied(self):
        self.receipt["project_id"]="other"
        with patch(MODULE+"get_job",return_value=self.job), self.assertRaises(PermissionError):
            import_into_approved_auto_stage(
                Path("unused"),"a"*32,self.receipt,{},{"TEXT":[],"CODE":[]},
                operator_approved=True)

    def test_candidate_sqlite_mismatch_refuses_qdrant_open(self):
        from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
        with (
            patch(MODULE+"get_job",return_value=self.job),
            patch(MODULE+"stage_directory",return_value=self.stage),
            patch(MODULE+"verify_candidate_stage_rows",
                  side_effect=IncrementalPlanError("mismatch")),
            patch(MODULE+"open_qdrant_local") as opened,
            self.assertRaises(IncrementalPlanError),
        ):
            import_into_approved_auto_stage(
                Path("unused"),"a"*32,self.receipt,{},
                {"TEXT":[],"CODE":[]},operator_approved=True)
        opened.assert_not_called()

    def test_redirected_staging_root_denied_before_qdrant(self):
        with (
            patch(MODULE+"get_job",return_value=self.job),
            patch(MODULE+"stage_directory",return_value=self.stage),
            patch("pathlib.Path.is_symlink",return_value=True),
            patch(MODULE+"open_qdrant_local") as opened,
            self.assertRaises(PermissionError),
        ):
            import_into_approved_auto_stage(
                Path("unused"),"a"*32,self.receipt,{},
                {"TEXT":[],"CODE":[]},operator_approved=True)
        opened.assert_not_called()

    def test_unprepared_stage_denied(self):
        (self.stage/"rag_index.sqlite3").unlink()
        with (
            patch(MODULE+"get_job",return_value=self.job),
            patch(MODULE+"stage_directory",return_value=self.stage),
            patch(MODULE+"open_qdrant_local") as opened,
        ):
            with self.assertRaises(PermissionError):
                import_into_approved_auto_stage(
                    Path("unused"),"a"*32,self.receipt,{},{"TEXT":[],"CODE":[]},
                    operator_approved=True)
            opened.assert_not_called()
