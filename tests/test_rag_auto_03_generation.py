"""RAG-AUTO-03 verified generation tests, all data in temporary workspace."""
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.runtime.auto_index_queue import create_draft,default_queue_path
from rag.runtime.auto_index_approval import build_auto_index_preview,approve_auto_index_draft
from rag.runtime.auto_index_worker import execute_auto_vector_batch
from rag.runtime.auto_index_generation import (
    AutoGenerationError,validate_reviewed_auto_generation,
    prepare_verified_auto_generation,verify_prepared_auto_generation,
)
from test_rag_auto_02_worker import fake_writer


class AutoGenerationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        self.root=self.home/"source"
        self.root.mkdir()
        (self.root/"README.md").write_bytes(b"# Indexing\r\nThe project is safe.\r\n")
        (self.root/"main.py").write_text("def project():\n  return 50\n",encoding="utf-8")
        self.project="auto-gen-test"
        self.queue=default_queue_path(self.home)
        draft=create_draft(self.queue,project_id=self.project,source_root=self.root,
                           idempotency_key="generation-test-123456",allow_write=True)
        self.job=draft["job_id"]
        review=build_auto_index_preview(self.project,self.root)
        approve_auto_index_draft(self.queue,self.job,review,
                                  confirmed_digest=review["review_sha256"],
                                  operator_approved=True,allow_write=True)
        public=patch("rag.runtime.auto_index_worker._public_generation",
                     return_value="test_public_untouched")
        public.start()
        self.addCleanup(public.stop)
        for _ in range(9):
            status=execute_auto_vector_batch(
                self.queue,self.job,execute=True,operator_approved=True,
                confirmation="RAG_AUTO_RUN:"+self.job,
                max_vectors=1,memory_probe=lambda:4096,
                semantic_guard_factory=nullcontext,model_writer=fake_writer,
            )
            if status["state"]=="READY_FOR_REVIEW":
                break
        self.assertEqual(status["state"],"READY_FOR_REVIEW")

    def prepare(self):
        return prepare_verified_auto_generation(
            self.queue,self.job,operator_approved=True,prepare_enabled=True,
        )

    def test_validate_and_prepare_snapshot(self):
        validated=validate_reviewed_auto_generation(self.queue,self.job)
        self.assertEqual(validated["sources"],2)
        data=self.prepare()
        self.assertFalse(data["catalog_updated"])
        self.assertFalse(data["public_pointer_updated"])
        final=verify_prepared_auto_generation(self.queue,self.job)
        self.assertTrue(final["verified"])
        self.assertEqual(final["counts"]["chunks"],validated["chunks"])
        self.assertTrue(Path(data["source_snapshot"],"README.md").read_bytes().startswith(b"# Indexing\r\n"))
        self.assertNotEqual(Path(data["generation"]).resolve(),Path(validated["stage"]).resolve())

    def test_mismatch_in_original_source_blocks_preparation(self):
        (self.root/"main.py").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.prepare()
        expected=self.queue.parent.parent/"projects"/self.project/"generations"
        self.assertFalse(expected.exists())

    def test_snapshot_corruption_detected(self):
        data=self.prepare()
        Path(data["source_snapshot"],"main.py").write_text("bad",encoding="utf-8")
        with self.assertRaises(AutoGenerationError):
            verify_prepared_auto_generation(self.queue,self.job)

    def test_generation_corruption_detected(self):
        data=self.prepare()
        Path(data["generation"],"rag-index-manifest.json").write_text("{}",encoding="utf-8")
        with self.assertRaises(AutoGenerationError):
            verify_prepared_auto_generation(self.queue,self.job)

    def test_no_overwriting_previous_generation(self):
        self.prepare()
        with self.assertRaises(AutoGenerationError):
            self.prepare()

    def test_requires_explicit_approval(self):
        with self.assertRaises(PermissionError):
            prepare_verified_auto_generation(self.queue,self.job)


if __name__=="__main__":
    unittest.main()
