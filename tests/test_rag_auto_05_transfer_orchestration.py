"""RAG-AUTO-05-E verification-bound transfer orchestration tests."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch,Mock

from rag.runtime.auto_index_incremental_transfer import transfer_verified_incremental_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

MODULE="rag.runtime.auto_index_incremental_transfer."


class TransferOrchestrationTests(TestCase):
    def setUp(self):
        self.fields={
            "baseline_text_model":"text-pin","candidate_text_model":"text-pin",
            "baseline_code_model":"code-pin","candidate_code_model":"code-pin",
            "operator_approved":True,
        }
        self.plan={
            "project_id":"lab-project",
            "candidate_reuse_chunk_receipt":{
                "mode":"CHUNK_RECEIPT_ONLY",
                "vector_copy_authorized":False,
                "project_id":"lab-project",
                "candidate_vector_count":1,
                "candidate_chunk_ids":{"keep.py":["cid"]},
            },
        }
        self.baseline={"verified":True,"project_id":"lab-project",
                       "generation":"C:/lab-baseline"}
        self.approved={"sources":[{"path":"keep.py","sha256":"a"*64,
                                   "index_kind":"CODE"}]}

    def go(self):
        with (
            patch(MODULE+"plan_reviewed_incremental_delta",return_value=self.plan),
            patch(MODULE+"verify_prepared_auto_generation",return_value=self.baseline),
            patch(MODULE+"read_reviewed_sources",return_value=self.approved),
            patch(MODULE+"Path.is_dir",return_value=True),
            patch(MODULE+"Path.is_symlink",return_value=False),
            patch(MODULE+"open_qdrant_local",return_value=Mock()) as source,
            patch(MODULE+"close_qdrant_local") as close,
            patch(MODULE+"read_reusable_vectors",return_value={"TEXT":[],"CODE":[{}]}) as read,
            patch(MODULE+"stage_directory",return_value=Path("C:/lab-destination")),
            patch(MODULE+"verify_isolated_reuse_batch",return_value={"revalidation_passed":True}),
            patch(MODULE+"import_into_approved_auto_stage",return_value={
                "vectors_written":1,"batch_id":"c"*32,"public_pointer_updated":False,
            }) as write,
        ):
            result=transfer_verified_incremental_batch(
                Path("unused"),"a"*32,"b"*32,**self.fields)
        return result,source,close,read,write

    def test_safe_job_bound_flow(self):
        result,source,close,read,write=self.go()
        self.assertEqual(result["vectors_written"],1)
        self.assertFalse(result["public_pointer_updated"])
        self.assertTrue(result["needs_post_copy_validation"])
        self.assertEqual(source.call_count,2)
        self.assertEqual(close.call_count,2)
        read.assert_called_once()
        write.assert_called_once()

    def test_corrupt_destination_refuses_success_after_copy(self):
        with (
            patch(MODULE+"plan_reviewed_incremental_delta",return_value=self.plan),
            patch(MODULE+"verify_prepared_auto_generation",return_value=self.baseline),
            patch(MODULE+"read_reviewed_sources",return_value=self.approved),
            patch(MODULE+"Path.is_dir",return_value=True),
            patch(MODULE+"Path.is_symlink",return_value=False),
            patch(MODULE+"open_qdrant_local",return_value=Mock()),
            patch(MODULE+"close_qdrant_local"),
            patch(MODULE+"read_reusable_vectors",return_value={"TEXT":[],"CODE":[{}]}),
            patch(MODULE+"stage_directory",return_value=Path("C:/lab-destination")),
            patch(MODULE+"import_into_approved_auto_stage",return_value={
                "batch_id":"c"*32,"vectors_written":1,"public_pointer_updated":False,
            }),
            patch(MODULE+"verify_isolated_reuse_batch",
                  return_value={"revalidation_passed":False}),
            self.assertRaisesRegex(IncrementalPlanError,"post-write"),
        ):
            transfer_verified_incremental_batch(Path("unused"),"a"*32,"b"*32,**self.fields)

    def test_requires_operator_approval_before_any_plan(self):
        with patch(MODULE+"plan_reviewed_incremental_delta") as plan:
            with self.assertRaises(PermissionError):
                transfer_verified_incremental_batch(
                    Path("unused"),"a"*32,"b"*32,
                    **{**self.fields,"operator_approved":False})
            plan.assert_not_called()

    def test_invalid_partition_index_fails_before_source_open(self):
        self.approved["sources"].append({
            "path":"readme.md","sha256":"b"*64,"index_kind":"TEXT"})
        self.plan["candidate_reuse_chunk_receipt"]["candidate_chunk_ids"]["readme.md"]=["other"]
        self.plan["candidate_reuse_chunk_receipt"]["candidate_vector_count"]=2
        with (
            patch(MODULE+"plan_reviewed_incremental_delta",return_value=self.plan),
            patch(MODULE+"verify_prepared_auto_generation",return_value=self.baseline),
            patch(MODULE+"read_reviewed_sources",return_value=self.approved),
            patch(MODULE+"Path.is_dir",return_value=True),
            patch(MODULE+"Path.is_symlink",return_value=False),
            patch(MODULE+"open_qdrant_local") as opened,
        ):
            with self.assertRaises(IncrementalPlanError):
                transfer_verified_incremental_batch(
                    Path("unused"),"a"*32,"b"*32,batch_index=99,**self.fields)
            opened.assert_not_called()
