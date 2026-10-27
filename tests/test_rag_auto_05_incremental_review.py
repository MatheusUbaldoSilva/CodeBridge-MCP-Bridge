"""RAG-AUTO-05-B read-only verified review adapter tests."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_incremental_review import plan_reviewed_incremental_delta

TARGET="rag.runtime.auto_index_incremental_review."


def source(path, digest, kind="CODE"):
    return {"path":path,"sha256":digest * 64,"index_kind":kind}


class ReviewedDeltaTests(TestCase):
    def setUp(self):
        self.old={"project_id":"lab-project","source_root":"C:/sources",
                  "requested_scope":"BOTH","approved":True,"state":"READY_FOR_REVIEW"}
        self.new={**self.old,"state":"QUEUED"}
        self.base_receipt={"source_root":"C:/sources","scope":"BOTH",
                           "sources":[source("old.py","a"),source("keep.py","b")],
                           "review_sha256":"a"*64}
        self.new_receipt={"source_root":"C:/sources","scope":"BOTH",
                          "sources":[source("keep.py","b"),source("new.py","c")],
                          "review_sha256":"b"*64}
        self.params=dict(
            baseline_text_model="text1",candidate_text_model="text1",
            baseline_code_model="code1",candidate_code_model="code1",
        )

    def run_plan(self):
        with (
            patch(TARGET+"get_job",side_effect=[self.old,self.new]),
            patch(TARGET+"verify_prepared_auto_generation",
                  return_value={"verified":True,"project_id":"lab-project",
                                "source_revision":"a"*64}) as verify,
            patch(TARGET+"read_reviewed_sources",
                  side_effect=[self.base_receipt,self.new_receipt]),
            patch(TARGET+"revalidate_auto_index_preview",
                  return_value={}) as revalidate,
            patch(TARGET+"inspect_reusable_manifest_chunks",
                  return_value={"candidate_vector_count":2,"vector_copy_authorized":False}),
        ):
            result=plan_reviewed_incremental_delta(
                Path("unused"),"a"*32,"b"*32,**self.params)
        return result,verify,revalidate

    def test_reviewed_delta_proposes_only_reuse(self):
        result,verify,revalidate=self.run_plan()
        self.assertEqual(result["eligible_reuse_sources"],["keep.py"])
        self.assertEqual(result["reindex_sources"],["new.py"])
        self.assertEqual(result["removed_sources"],["old.py"])
        self.assertFalse(result["reuse_authorized"])
        self.assertFalse(result["worker_started"])
        self.assertTrue(result["baseline_verified"])
        self.assertTrue(result["candidate_receipt_revalidated"])
        verify.assert_called_once()
        revalidate.assert_called_once()

    def test_cross_project_and_public_project_forbidden(self):
        for baseline,new in (
            ({**self.old,"project_id":"first"},self.new),
            ({**self.old,"project_id":"codebridge"},
             {**self.new,"project_id":"codebridge"}),
        ):
            with self.subTest(project=baseline["project_id"]), patch(
                TARGET+"get_job",side_effect=[baseline,new]
            ), self.assertRaises(IncrementalPlanError):
                plan_reviewed_incremental_delta(Path("unused"),
                    "a"*32,"b"*32,**self.params)

    def test_unapproved_candidate_rejected_before_generation_read(self):
        candidate={**self.new,"approved":False}
        with patch(TARGET+"get_job",side_effect=[self.old,candidate]), patch(
                TARGET+"verify_prepared_auto_generation") as verify:
            with self.assertRaises(IncrementalPlanError):
                plan_reviewed_incremental_delta(Path("unused"),
                    "a"*32,"b"*32,**self.params)
            verify.assert_not_called()

    def test_source_root_and_scope_mismatch(self):
        for candidate in (
            {**self.new,"source_root":"C:/other"},
            {**self.new,"requested_scope":"CODE"},
        ):
            with patch(TARGET+"get_job",side_effect=[self.old,candidate]):
                with self.assertRaises(IncrementalPlanError):
                    plan_reviewed_incremental_delta(Path("unused"),
                        "a"*32,"b"*32,**self.params)

    def test_source_change_after_approval_fails_closed(self):
        with (
            patch(TARGET+"get_job",side_effect=[self.old,self.new]),
            patch(TARGET+"verify_prepared_auto_generation",
                  return_value={"verified":True,"project_id":"lab-project",
                                "source_revision":"a"*64}),
            patch(TARGET+"read_reviewed_sources",
                  side_effect=[self.base_receipt,self.new_receipt]),
            patch(TARGET+"revalidate_auto_index_preview",
                  side_effect=ValueError("source changed")),
            patch(TARGET+"inspect_reusable_manifest_chunks"),
            self.assertRaisesRegex(ValueError,"source changed"),
        ):
            plan_reviewed_incremental_delta(Path("unused"),
                    "a"*32,"b"*32,**self.params)
