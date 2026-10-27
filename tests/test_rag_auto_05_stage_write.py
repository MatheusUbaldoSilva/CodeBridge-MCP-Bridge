"""RAG-AUTO-05-E bounded isolated stage writer contract tests."""
import unittest
from unittest.mock import Mock, patch
from rag.runtime.auto_index_incremental_stage_write import import_verified_reuse_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError


class StageWriteTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock()
        self.client.retrieve.return_value=[]
        self.receipt={}
        self.sources={}
        self.records={"TEXT":[{"id":"point-1","vector":[0.5],"payload":{}}],
                      "CODE":[]}
        self.kwargs=dict(isolated_destination=True,allow_stage_write=True)
        self.proof={"checked_vectors":1}

    def write(self, **overrides):
        with patch(
            "rag.runtime.auto_index_incremental_stage_write.validate_reusable_point_records",
            return_value=self.proof,
        ), patch("qdrant_client.models.PointStruct",side_effect=lambda **kwargs:kwargs):
            return import_verified_reuse_batch(
                self.client,self.receipt,self.sources,self.records,
                **{**self.kwargs,**overrides},
            )

    def test_copy_to_provided_client_only(self):
        result=self.write()
        self.assertEqual(result["vectors_written"],1)
        self.assertFalse(result["public_pointer_updated"])
        self.assertTrue(result["requires_staging_revalidation"])
        self.client.upsert.assert_called_once()
        self.assertEqual(self.client.upsert.call_args.kwargs["collection_name"],"text")

    def test_no_write_without_explicit_isolation_and_consent(self):
        for override in ({"isolated_destination":False},
                         {"allow_stage_write":False}):
            with self.subTest(override=override), self.assertRaises(PermissionError):
                self.write(**override)
        self.client.upsert.assert_not_called()

    def test_existing_destination_point_rejected_before_upsert(self):
        self.client.retrieve.return_value=[Mock()]
        with self.assertRaises(IncrementalPlanError):
            self.write()
        self.client.upsert.assert_not_called()

    def test_invalid_batch_size_denied(self):
        for count in (0,257,True):
            with self.subTest(count=count), self.assertRaises(IncrementalPlanError):
                self.write(max_vectors=count)
        self.client.upsert.assert_not_called()

    def test_cross_collection_batch_refused_before_write(self):
        self.records["CODE"]=[{"id":"point-2","vector":[0.2],"payload":{}}]
        self.proof={"checked_vectors":2}
        with self.assertRaises(IncrementalPlanError):
            self.write()
        self.client.upsert.assert_not_called()

    def test_batch_larger_than_limit_denied(self):
        self.proof={"checked_vectors":2}
        with self.assertRaises(IncrementalPlanError):
            self.write(max_vectors=1)
        self.client.upsert.assert_not_called()
