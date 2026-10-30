import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_preflight import inspect_private_deletion_preflight,PrivateDeletionPreflightError
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap,DeletionSwapError

class PrivatePreflightTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version":1,"projects":{
            "demo":{"project_id":"demo","enabled":True,"source_revision":"old",
                    "generation_directory":"old-generation"},
            "other":{"project_id":"other","enabled":True,"source_revision":"other",
                    "generation_directory":"other-generation"}}}))
        self.pointer.write_text('{"schema_version":1,"generation":"stable"}')
        self.candidate={"index_family":"RAG_DEL_01","project_id":"demo",
            "enabled":True,"source_revision":"new","generation_directory":"new-generation"}
        self.before=self.catalog.read_bytes()
        self.public=self.pointer.read_bytes()
    def preflight(self):
        return inspect_private_deletion_preflight(self.catalog,self.pointer,
                                                   "demo","old",self.candidate)
    def test_read_only_valid(self):
        result=self.preflight()
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["catalog_modified"])
        self.assertFalse(result["candidate_verified"])
        self.assertEqual(self.catalog.read_bytes(),self.before)
        self.assertEqual(self.pointer.read_bytes(),self.public)
    def test_stale_revision_denied(self):
        with self.assertRaises(ValueError):
            inspect_private_deletion_preflight(self.catalog,self.pointer,
                                               "demo","stale",self.candidate)
    def test_pending_journal_refused(self):
        with self.assertRaises(DeletionSwapError):
            laboratory_swap("demo","old",{"project_id":"demo","enabled":True,
                "source_revision":"new","generation_directory":"new-generation"},
                catalog_file=self.catalog,public_pointer=self.pointer,
                operator_approved=True,laboratory_mode=True,_fail_at="before")
        with self.assertRaises(PrivateDeletionPreflightError):self.preflight()
    def test_tampered_rolled_back_journal_backup_refused(self):
        from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback
        result=laboratory_swap("demo","old",{
            "project_id":"demo","enabled":True,"source_revision":"new",
            "generation_directory":"new-generation"},
            catalog_file=self.catalog,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)
        laboratory_rollback(result["transaction"],catalog_file=self.catalog,
            public_pointer=self.pointer,operator_approved=True,laboratory_mode=True)
        backup=next(self.root.glob("rag-del-*.previous.json"))
        backup.write_bytes(b"modified backup")
        with self.assertRaises(PrivateDeletionPreflightError):
            self.preflight()

    def test_wrong_family_denied(self):
        self.candidate["index_family"]="RAG_AUTO_03"
        with self.assertRaises(PrivateDeletionPreflightError):self.preflight()
    def test_public_namespace_denied(self):
        with self.assertRaises(PrivateDeletionPreflightError):
            inspect_private_deletion_preflight(self.catalog,self.pointer,
                "codebridge","old",self.candidate)
