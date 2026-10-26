"""RAG-AUTO-01.3: source-scoped operator approval tests, no model starts."""
from contextlib import closing
import hashlib
from pathlib import Path
import tempfile
import unittest

from rag.runtime.auto_index_queue import (
    AutoIndexQueueError, create_draft, default_queue_path,
    get_job, inspect_queue, list_events,
)
from rag.runtime.auto_index_approval import (
    approve_auto_index_draft,build_auto_index_preview,
    revalidate_auto_index_preview,read_reviewed_sources,
)


class AutoIndexApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/"project"
        self.root.mkdir()
        (self.root/"README.md").write_text("Hello CodeBridge RAG\n",encoding="utf-8")
        (self.root/"main.py").write_text("def answer():\n    return 42\n",encoding="utf-8")
        self.db=default_queue_path(self.base)
        self.project="project-one"
        self.job=create_draft(self.db,project_id=self.project,source_root=self.root,
                              idempotency_key="approval-1234567890",allow_write=True)
        self.preview=build_auto_index_preview(self.project,self.root)

    def approve(self,**kwargs):
        args={"confirmed_digest":self.preview["review_sha256"],
              "operator_approved":True,"allow_write":True}
        args.update(kwargs)
        return approve_auto_index_draft(
            self.db,self.job["job_id"],self.preview,**args,
        )

    def test_preview_contains_only_eligible_files(self):
        self.assertEqual(self.preview["candidate_count"],2)
        self.assertEqual({x["path"] for x in self.preview["sources"]},{"README.md","main.py"})
        self.assertEqual(revalidate_auto_index_preview(self.preview)["review_sha256"],
                         self.preview["review_sha256"])
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"DRAFT")

    def test_operator_approval_durably_queues_without_worker(self):
        result=self.approve()
        self.assertEqual(result["state"],"QUEUED")
        self.assertFalse(result["worker_started"])
        self.assertFalse(result["publication_authorized"])
        self.assertTrue(result["job_enqueued"])
        stored=get_job(self.db,self.job["job_id"])
        self.assertEqual(stored["state"],"QUEUED")
        self.assertTrue(stored["approved"])
        self.assertEqual(stored["file_count"],2)
        receipt=read_reviewed_sources(self.db,self.job["job_id"])
        self.assertEqual(receipt["review_sha256"],self.preview["review_sha256"])
        self.assertEqual(len(receipt["sources"]),2)
        self.assertEqual([x["event_type"] for x in list_events(self.db,self.job["job_id"])],
                         ["DRAFT_CREATED","SOURCE_REVIEW_CONFIRMED"])
        self.assertEqual(inspect_queue(self.db)["by_state"],{"QUEUED":1})

    def test_unapproved_or_mismatched_confirmation_blocks(self):
        with self.assertRaises(PermissionError):
            self.approve(operator_approved=False)
        with self.assertRaises(PermissionError):
            self.approve(allow_write=False)
        with self.assertRaises(ValueError):
            self.approve(confirmed_digest="0"*64)
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"DRAFT")

    def test_changes_between_preview_and_approval_block(self):
        (self.root/"main.py").write_text("print('updated')\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            self.approve()
        self.assertEqual(get_job(self.db,self.job["job_id"])["state"],"DRAFT")

    def test_changed_scope_blocks(self):
        with self.assertRaises(ValueError):
            preview=build_auto_index_preview(self.project,self.root,scope="DANGEROUS")
        self.preview["sources"]=self.preview["sources"][:1]
        with self.assertRaises(ValueError):
            self.approve()
        self.assertFalse(get_job(self.db,self.job["job_id"])["approved"])

    def test_project_mismatch_blocked(self):
        preview=build_auto_index_preview("another-project",self.root)
        with self.assertRaises(AutoIndexQueueError):
            approve_auto_index_draft(
                self.db,self.job["job_id"],preview,
                confirmed_digest=preview["review_sha256"],
                operator_approved=True,allow_write=True,
            )
        self.assertFalse(get_job(self.db,self.job["job_id"])["approved"])

    def test_second_approval_does_not_duplicate_receipt(self):
        self.approve()
        with self.assertRaises(AutoIndexQueueError):
            self.approve()
        self.assertEqual(len(list_events(self.db,self.job["job_id"])),2)

    def test_receipt_unavailable_before_approval(self):
        with self.assertRaises(PermissionError):
            read_reviewed_sources(self.db,self.job["job_id"])

    def test_hidden_sensitive_file_is_not_in_approved_snapshot(self):
        (self.root/".env").write_text("OPENAI_API_KEY=an-example-secret",encoding="utf-8")
        preview=build_auto_index_preview(self.project,self.root)
        self.assertNotIn(".env",{x["path"] for x in preview["sources"]})
        self.assertGreaterEqual(preview["denied_count"]+preview["sensitive_count"],1)

    def test_explicit_denied_file_never_approved(self):
        (self.root/".env").write_text("SECRET=1",encoding="utf-8")
        with self.assertRaises(ValueError):
            build_auto_index_preview(self.project,self.root,paths=[".env"])

    def test_revalidation_blocks_added_eligible_file_when_whole_tree_selected(self):
        # The frozen preview is exact for the approved paths. New files must
        # be treated as a later operation, not silently added to the receipt.
        (self.root/"new_feature.py").write_text("print(3)\n",encoding="utf-8")
        self.approve()
        receipt=read_reviewed_sources(self.db,self.job["job_id"])
        self.assertNotIn("new_feature.py",{x["path"] for x in receipt["sources"]})


if __name__=="__main__":
    unittest.main()
