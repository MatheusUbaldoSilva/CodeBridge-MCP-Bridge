"""RAG-AUTO-05-F integration of supervised entry with real SQLite lease."""
from pathlib import Path
from rag.models.backend_policy import TEXT_MODEL_REVISION
from rag.models.code_backend_policy import CODE_MODEL_REVISION
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_supervisor import inspect_index_supervisor
from rag.runtime.auto_index_staging import stage_directory
from rag.runtime.auto_index_incremental_supervised import run_supervised_incremental_batch

class SupervisedRealQueueTests(unittest.TestCase):
    def test_real_queue_lease_stage_and_release(self):
        with tempfile.TemporaryDirectory(prefix="auto05-supervised-lab-") as tmp:
            base=Path(tmp)
            root=base/"sources"
            root.mkdir()
            (root/"code.py").write_text("def example(): return 1\n",encoding="utf-8")
            queue=default_queue_path(base)
            draft=create_draft(queue,project_id="supervised-lab",
                source_root=root,idempotency_key="supervised-lab-123456789",
                allow_write=True)
            preview=build_auto_index_preview("supervised-lab",root)
            approve_auto_index_draft(queue,draft["job_id"],preview,
                confirmed_digest=preview["review_sha256"],
                operator_approved=True,allow_write=True)
            with (
                patch("rag.runtime.auto_index_incremental_supervised._free_ram_mib",return_value=4096),
                patch("rag.runtime.auto_index_incremental_supervised.inventory_auto_vectors",return_value={"complete":False}),
                patch("rag.runtime.auto_index_incremental_supervised._begin_batch"),
                patch("rag.runtime.auto_index_incremental_supervised.update_auto_checkpoint",return_value={"state":"QUEUED"}),
                patch("rag.runtime.auto_index_incremental_supervised._public_generation",
                      return_value="public-generation-unchanged"),
                patch("rag.runtime.auto_index_incremental_supervised.execute_fenced_incremental_batch",
                      return_value={"vectors_written":1,"public_pointer_updated":False}) as transfer,
            ):
                result=run_supervised_incremental_batch(
                    queue,"a"*32,draft["job_id"],execute=True,
                    operator_approved=True,
                    confirmation="RAG_AUTO_INCREMENTAL_RUN:"+draft["job_id"],
                    baseline_code_model=CODE_MODEL_REVISION,candidate_code_model=CODE_MODEL_REVISION,
                    baseline_text_model=TEXT_MODEL_REVISION,candidate_text_model=TEXT_MODEL_REVISION,
                )
            self.assertEqual(result["vectors_written"],1)
            self.assertEqual(result["public_generation_unchanged"],
                             "public-generation-unchanged")
            transfer.assert_called_once()
            self.assertEqual(inspect_index_supervisor(queue)["state"],"NOT_RESERVED")
            stage=stage_directory(queue,draft["job_id"])
            self.assertTrue((stage/"rag_index.sqlite3").is_file())
            self.assertTrue((stage/"qdrant").is_dir())
