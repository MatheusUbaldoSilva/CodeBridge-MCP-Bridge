import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap,DeletionSwapError
from rag.runtime.knowledge_deletion_recovery_lab import inspect_laboratory_transactions

class RecoveryAuditLabTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.catalog.write_text(json.dumps({"schema_version":1,"projects":{
            "demo":{"project_id":"demo","enabled":True,"source_revision":"old","generation_directory":"old"}
        }}))
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"public"}))
        self.new={"project_id":"demo","enabled":True,"source_revision":"new","generation_directory":"new"}
    def run_swap(self,**flags):
        return laboratory_swap("demo","old",self.new,catalog_file=self.catalog,
            public_pointer=self.pointer,operator_approved=True,laboratory_mode=True,**flags)
    def inspect(self):
        return inspect_laboratory_transactions(self.catalog,self.pointer)
    def test_empty_inventory(self):
        self.assertEqual(self.inspect(),[])
    def test_active_transaction(self):
        self.run_swap()
        result=self.inspect()
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["disposition"],"CATALOG_AT_NEW_REVISION")
        self.assertFalse(result[0]["repair_performed"])
    def test_interrupted_before_switch(self):
        with self.assertRaises(DeletionSwapError):
            self.run_swap(_fail_at="before")
        result=self.inspect()
        self.assertEqual(result[0]["state"],"PREPARED")
        self.assertEqual(result[0]["disposition"],"CATALOG_AT_OLD_REVISION")
    def test_interrupted_after_switch(self):
        with self.assertRaises(DeletionSwapError):
            self.run_swap(_fail_at="after")
        result=self.inspect()
        self.assertEqual(result[0]["state"],"PREPARED")
        self.assertEqual(result[0]["disposition"],"CATALOG_AT_NEW_REVISION")
    def test_changed_pointer_requires_review(self):
        self.run_swap()
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"changed"}))
        self.assertTrue(self.inspect()[0]["requires_manual_review"])
    def test_changed_catalog_requires_review(self):
        self.run_swap()
        self.catalog.write_text(json.dumps({"schema_version":1,"projects":{}}))
        self.assertTrue(self.inspect()[0]["requires_manual_review"])
    def test_tampered_journal_rejected_by_audit_and_rollback(self):
        from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback
        result=self.run_swap()
        journal=Path(result["journal"])
        data=json.loads(journal.read_text(encoding="utf-8"))
        data["project_id"]="foreign"
        journal.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(DeletionSwapError):
            self.inspect()
        with self.assertRaises(DeletionSwapError):
            laboratory_rollback(result["transaction"],catalog_file=self.catalog,
                public_pointer=self.pointer,operator_approved=True,laboratory_mode=True)

    def test_tampered_backup_refused(self):
        self.run_swap()
        next(self.root.glob("*.previous.json")).write_text("tampered")
        with self.assertRaises(DeletionSwapError):
            self.inspect()
