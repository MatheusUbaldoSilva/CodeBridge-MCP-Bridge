"""RAG-AUTO-05-F actual SQLite supervisor fence smoke, no vector writes."""
from pathlib import Path
from contextlib import nullcontext
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft, default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview, approve_auto_index_draft
from rag.runtime.auto_index_supervisor import (
    reserve_index_supervisor, release_index_supervisor,
)
from rag.runtime.auto_index_incremental_fenced import execute_fenced_incremental_batch


class ActualFencedQueueTests(unittest.TestCase):
    def test_fenced_approved_queue_refuses_released_owner(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-fence-") as tmp:
            base=Path(tmp)
            root=base/"project"
            root.mkdir()
            (root/"source.py").write_text("print('safe')\n",encoding="utf-8")
            queue=default_queue_path(base)
            job=create_draft(queue,project_id="fence-lab",source_root=root,
                idempotency_key="fencing-smoke-lab-1234",allow_write=True)
            preview=build_auto_index_preview("fence-lab",root)
            approve_auto_index_draft(queue,job["job_id"],preview,
                confirmed_digest=preview["review_sha256"],
                operator_approved=True,allow_write=True)
            lease=reserve_index_supervisor(
                queue,job["job_id"],operator_approved=True,reservation_enabled=True,
            )
            base_args=dict(queue_path=queue,baseline_job_id="a"*32,
                candidate_job_id=job["job_id"],
                lease_token=lease["lease_token"],generation=lease["generation"],
                operator_approved=True,baseline_text_model="text",
                candidate_text_model="text",baseline_code_model="code",
                candidate_code_model="code")
            with patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",return_value=nullcontext()), patch(
                "rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
                return_value={"vectors_written":0,"public_pointer_updated":False},
            ) as transfer:
                result=execute_fenced_incremental_batch(**base_args)
                self.assertTrue(result["supervisor_fence_rechecked"])
                transfer.assert_called_once()
            released=release_index_supervisor(
                queue,job["job_id"],lease["lease_token"],lease["generation"])
            self.assertTrue(released["accepted"])
            with patch("rag.runtime.auto_index_incremental_fenced.production_generation_lock",return_value=nullcontext()), patch(
                "rag.runtime.auto_index_incremental_fenced.transfer_verified_incremental_batch",
            ) as transfer, self.assertRaises(PermissionError):
                execute_fenced_incremental_batch(**base_args)
                transfer.assert_not_called()
