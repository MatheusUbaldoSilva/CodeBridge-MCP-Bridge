from unittest import TestCase
from unittest.mock import patch,Mock
from rag.runtime.knowledge_deletion_vector_copy import copy_survivor_batch
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

class SurvivorCopyTests(TestCase):
    def setUp(self):
        self.source=Mock()
        self.target=Mock()
        self.receipt={"project_id":"demo","candidate_vector_count":1}
        self.plan={"state":"SURVIVOR_RECEIPTS_ONLY","project_id":"demo",
                   "activation_authorized":False,
                   "batches":[self.receipt],"sources":{"sources":[]}}

    def call(self,**kwargs):
        opts={"verified_source":True,"isolated_staging":True,
              "operator_approved":True}
        opts.update(kwargs)
        return copy_survivor_batch(self.source,self.target,self.plan,0,**opts)

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    @patch("rag.runtime.knowledge_deletion_vector_copy.read_reusable_vectors")
    def test_rechecks_after_import(self, read,write):
        read.return_value={"TEXT":[],"CODE":[{"id":"abc"}]}
        write.return_value={"vectors_written":1}
        result=self.call()
        self.assertEqual(result["vectors_verified"],1)
        self.assertEqual(read.call_count,2)
        self.assertEqual(write.call_count,1)
        self.assertTrue(result["requires_durable_checkpoint"])
        self.assertFalse(result["generation_activated"])

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    def test_no_approval_no_write(self,write):
        with self.assertRaises(PermissionError):
            self.call(operator_approved=False)
        write.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    def test_same_client_no_write(self,write):
        self.target=self.source
        with self.assertRaises(IncrementalPlanError):
            self.call()
        write.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    def test_public_project_no_write(self,write):
        self.plan["project_id"]="codebridge"
        with self.assertRaises(IncrementalPlanError):
            self.call()
        write.assert_not_called()

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    @patch("rag.runtime.knowledge_deletion_vector_copy.read_reusable_vectors")
    def test_readback_failure_refused(self,read,write):
        read.side_effect=[{"TEXT":[],"CODE":[{"id":"abc"}]},
                          {"TEXT":[],"CODE":[]}]
        write.return_value={"vectors_written":1}
        with self.assertRaises(IncrementalPlanError):
            self.call()

    @patch("rag.runtime.knowledge_deletion_vector_copy.import_verified_reuse_batch")
    def test_invalid_index_no_write(self,write):
        with self.assertRaises(IncrementalPlanError):
            copy_survivor_batch(self.source,self.target,self.plan,True,
               verified_source=True,isolated_staging=True,operator_approved=True)
        write.assert_not_called()
