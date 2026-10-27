"""RAG-AUTO-05-F full approved baseline -> supervised reuse canary.

All sources, queue, Qdrant and immutable generation live under temp dir.
Synthetic valid embeddings avoid model load and public index access.
"""
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft,default_queue_path,get_job,AutoIndexQueueError
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_generation import (
    prepare_verified_auto_generation,verify_prepared_auto_generation,
)
from rag.runtime.auto_index_worker import execute_auto_vector_batch
from rag.runtime.auto_index_incremental_supervised import run_supervised_incremental_batch
from rag.runtime.auto_index_batch import inventory_auto_vectors
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError
from rag.runtime.auto_index_staging import stage_directory
from rag.models.backend_policy import TEXT_MODEL_REVISION
from rag.models.code_backend_policy import CODE_MODEL_REVISION
from test_rag_auto_02_worker import fake_writer


class FullApprovedReuseIntegrationTests(unittest.TestCase):
    def test_baseline_verified_generation_to_supervised_candidate(self):
        with tempfile.TemporaryDirectory(prefix="ragauto05-full-approved-") as tmp:
            home=Path(tmp)
            source=home/"files"
            source.mkdir()
            (source/"single.py").write_text("def meaning():\n  return 42\n",encoding="utf-8")
            (source/"README.md").write_text("# Canary\\nReused TEXT sample\\n",encoding="utf-8")
            queue=default_queue_path(home)
            project="auto05-full-integration"
            def approve(key):
                draft=create_draft(queue,project_id=project,source_root=source,
                    idempotency_key=key,allow_write=True)
                preview=build_auto_index_preview(project,source)
                approve_auto_index_draft(queue,draft["job_id"],preview,
                    confirmed_digest=preview["review_sha256"],
                    operator_approved=True,allow_write=True)
                return draft["job_id"]
            old=approve("full-baseline-approval-12345")
            with patch("rag.runtime.auto_index_worker._public_generation",
                       return_value="public-unchanged"):
                for _ in range(8):
                    completed=execute_auto_vector_batch(
                        queue,old,execute=True,operator_approved=True,
                        confirmation="RAG_AUTO_RUN:"+old,max_vectors=1,
                        memory_probe=lambda:4096,
                        semantic_guard_factory=nullcontext,
                        model_writer=fake_writer,
                    )
                    if completed["state"]=="READY_FOR_REVIEW":
                        break
            self.assertEqual(completed["state"],"READY_FOR_REVIEW")
            built=prepare_verified_auto_generation(
                queue,old,operator_approved=True,prepare_enabled=True)
            self.assertTrue(verify_prepared_auto_generation(queue,old)["verified"])
            new=approve("full-candidate-approval-1234")
            with (
                patch("rag.runtime.auto_index_incremental_supervised._free_ram_mib",
                      return_value=4096),
                patch("rag.runtime.auto_index_incremental_supervised._public_generation",
                      return_value="public-unchanged"),
                self.assertRaises(IncrementalPlanError),
            ):
                run_supervised_incremental_batch(
                    queue,old,new,execute=True,operator_approved=True,
                    confirmation="RAG_AUTO_INCREMENTAL_RUN:"+new,
                    max_vectors=1,batch_index=99,
                    baseline_text_model=TEXT_MODEL_REVISION,
                    candidate_text_model=TEXT_MODEL_REVISION,
                    baseline_code_model=CODE_MODEL_REVISION,
                    candidate_code_model=CODE_MODEL_REVISION,
                )
            self.assertEqual(get_job(queue,new)["state"],"QUEUED")
            with (
                patch("rag.runtime.auto_index_incremental_supervised._free_ram_mib",
                      return_value=4096),
                patch("rag.runtime.auto_index_incremental_supervised._public_generation",
                      return_value="public-unchanged"),
            ):
                first=run_supervised_incremental_batch(
                    queue,old,new,execute=True,operator_approved=True,
                    confirmation="RAG_AUTO_INCREMENTAL_RUN:"+new,max_vectors=1,
                    batch_index=0,
                    baseline_text_model=TEXT_MODEL_REVISION,
                    candidate_text_model=TEXT_MODEL_REVISION,
                    baseline_code_model=CODE_MODEL_REVISION,
                    candidate_code_model=CODE_MODEL_REVISION,
                )
                self.assertEqual(first["state"],"QUEUED")
                transferred=run_supervised_incremental_batch(
                    queue,old,new,execute=True,operator_approved=True,
                    confirmation="RAG_AUTO_INCREMENTAL_RUN:"+new,max_vectors=1,
                    batch_index=1,
                    baseline_text_model=TEXT_MODEL_REVISION,
                    candidate_text_model=TEXT_MODEL_REVISION,
                    baseline_code_model=CODE_MODEL_REVISION,
                    candidate_code_model=CODE_MODEL_REVISION,
                )
            self.assertGreater(transferred["vectors_written"],0)
            self.assertTrue(transferred["post_copy_verification"]["revalidation_passed"])
            self.assertFalse(transferred["public_pointer_updated"])
            candidate=inventory_auto_vectors(queue,new)
            baseline=inventory_auto_vectors(queue,old)
            self.assertEqual(candidate["code_ids"],baseline["code_ids"])
            self.assertEqual(candidate["text_ids"],baseline["text_ids"])
            self.assertTrue(candidate["complete"])
            self.assertTrue(stage_directory(queue,new).is_dir())
            self.assertEqual(get_job(queue,new)["state"],"READY_FOR_REVIEW")
            self.assertEqual(transferred["state"],"READY_FOR_REVIEW")
            # The completed job must not be reopened through the same consent.
            with (
                patch("rag.runtime.auto_index_incremental_supervised._free_ram_mib",
                      return_value=4096),
                patch("rag.runtime.auto_index_incremental_supervised._public_generation",
                      return_value="public-unchanged"),
            ):
                with self.assertRaises((PermissionError,AutoIndexQueueError)):
                    run_supervised_incremental_batch(
                        queue,old,new,execute=True,operator_approved=True,
                        confirmation="RAG_AUTO_INCREMENTAL_RUN:"+new,
                        baseline_text_model=TEXT_MODEL_REVISION,
                        candidate_text_model=TEXT_MODEL_REVISION,
                        baseline_code_model=CODE_MODEL_REVISION,
                        candidate_code_model=CODE_MODEL_REVISION,
                    )
            self.assertEqual(get_job(queue,new)["state"],"READY_FOR_REVIEW")
