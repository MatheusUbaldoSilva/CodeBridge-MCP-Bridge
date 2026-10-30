"""Negative tests for survivor Qdrant candidate semantic verification."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
from types import SimpleNamespace
from rag.runtime.knowledge_deletion_semantics import verify_candidate_vector_semantics
from rag.runtime.auto_index_incremental_plan import IncrementalPlanError

class CandidateSemanticAuditTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=Mock()
        self.client.count.return_value=SimpleNamespace(count=0)
        self.patchers=[]
        for name,retval in [
            ("rag.runtime.knowledge_deletion_semantics.load_index_manifest",
             SimpleNamespace(entries=())),
            ("rag.runtime.knowledge_deletion_semantics.inspect_deletion_generation_structure",
             {"chunks":0}),
            ("rag.runtime.knowledge_deletion_semantics.partition_reuse_receipt",[])
        ]:
            p=patch(name,return_value=retval)
            p.start();self.addCleanup(p.stop)
    def call(self,**kwargs):
        return verify_candidate_vector_semantics(self.root,"demo",self.client,**kwargs)
    def test_empty_candidate_requires_zero_vectors(self):
        result=self.call()
        self.assertEqual(result["vectors_verified"],0)
        self.assertFalse(result["activation_authorized"])
    def test_extra_vector_is_rejected(self):
        self.client.count.side_effect=[SimpleNamespace(count=0),SimpleNamespace(count=1)]
        with self.assertRaises(IncrementalPlanError):self.call()
    def test_public_project_is_rejected(self):
        with self.assertRaises(IncrementalPlanError):
            verify_candidate_vector_semantics(self.root,"codebridge",self.client)
    def test_invalid_max_batch_is_rejected(self):
        for value in (0,257,True):
            with self.subTest(value=value):
                with self.assertRaises(IncrementalPlanError):self.call(max_batch=value)
    def test_missing_client_is_rejected(self):
        with self.assertRaises(IncrementalPlanError):
            verify_candidate_vector_semantics(self.root,"demo",None)


