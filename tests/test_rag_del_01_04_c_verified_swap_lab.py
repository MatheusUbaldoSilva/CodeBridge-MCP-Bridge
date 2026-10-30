import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from rag.runtime.knowledge_deletion_verified_swap_lab import laboratory_verified_swap
from rag.runtime.knowledge_deletion_generation import DeletionGenerationUnavailable
from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback

class VerifiedSwapLabTests(TestCase):
    def setUp(self):
        t=TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version":1,"projects":{
            "demo":{"project_id":"demo","enabled":True,"source_revision":"a"*64,
                    "generation_directory":"old"}}}))
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"public"}))
        self.old_pointer=self.pointer.read_bytes()
        self.new={"index_family":"RAG_DEL_01","project_id":"demo","enabled":True,
            "transaction_id":"b"*32,"source_revision":"c"*64,
            "generation_directory":str(self.root/"generations"/("del_"+"b"*32)),
            "source_directory":str(self.root/"snapshots"/("source_"+"b"*32))}
    def run_swap(self,**kwargs):
        return laboratory_verified_swap("demo","a"*64,self.new,
            catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True,**kwargs)
    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    def test_verified_candidate_switch_and_rollback(self,verify):
        result=self.run_swap()
        verify.assert_called_once()
        self.assertEqual(result["state"],"LAB_SWAP_ACTIVE")
        self.assertEqual(self.pointer.read_bytes(),self.old_pointer)
        restored=laboratory_rollback(result["transaction"],
            catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)
        self.assertEqual(restored["state"],"LAB_ROLLBACK_COMPLETE")
    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    def test_verification_failure_preserves_catalog(self,verify):
        before=self.catalog.read_bytes()
        verify.side_effect=DeletionGenerationUnavailable("bad receipt")
        with self.assertRaises(DeletionGenerationUnavailable):self.run_swap()
        self.assertEqual(before,self.catalog.read_bytes())
        self.assertEqual(list(self.root.glob("rag-del-*.journal.json")),[])
    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    def test_wrong_family_fails_before_verification(self,verify):
        self.new["index_family"]="RAG_AUTO_03"
        with self.assertRaises(Exception): self.run_swap()
        verify.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_verified_swap_lab.verify_deletion_generation")
    def test_no_approval_fails_before_verification(self,verify):
        with self.assertRaises(PermissionError):
            laboratory_verified_swap("demo","a"*64,self.new,catalog_file=self.catalog,
                public_pointer=self.pointer,operator_approved=False,laboratory_mode=True)
        verify.assert_not_called()
