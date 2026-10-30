import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap,laboratory_rollback,DeletionSwapError

class LabCatalogSwitchTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.cat=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.before={"schema_version":1,"projects":{
            "demo":{"project_id":"demo","enabled":True,"source_revision":"old","generation_directory":"old"},
            "other":{"project_id":"other","enabled":True,"source_revision":"other","generation_directory":"other"}}}
        self.cat.write_text(json.dumps(self.before))
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"public"}))
        self.public=self.pointer.read_bytes()
        self.new={"project_id":"demo","enabled":True,"source_revision":"new","generation_directory":"new"}

    def swap(self,**options):
        return laboratory_swap("demo","old",self.new,catalog_file=self.cat,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True,**options)

    def undo(self,transaction):
        return laboratory_rollback(transaction,catalog_file=self.cat,public_pointer=self.pointer,
            operator_approved=True,laboratory_mode=True)

    def test_swap_preserves_other_and_rollback(self):
        result=self.swap()
        data=json.loads(self.cat.read_text())
        self.assertEqual(data["projects"]["demo"],self.new)
        self.assertEqual(data["projects"]["other"],self.before["projects"]["other"])
        self.assertEqual(self.pointer.read_bytes(),self.public)
        undone=self.undo(result["transaction"])
        self.assertEqual(undone["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(json.loads(self.cat.read_text()),self.before)
        self.assertEqual(self.pointer.read_bytes(),self.public)
        self.assertEqual(self.undo(result["transaction"])["state"],"ALREADY_ROLLED_BACK")

    def test_failure_before_switch_can_rollback(self):
        with self.assertRaises(DeletionSwapError):
            self.swap(_fail_at="before")
        journal=list(self.root.glob("rag-del-*.journal.json"))
        self.assertEqual(len(journal),1)
        tid=journal[0].name.split("-")[2].split(".")[0]
        self.assertEqual(self.undo(tid)["state"],"ALREADY_ROLLED_BACK")
        self.assertEqual(json.loads(self.cat.read_text()),self.before)

    def test_failure_after_switch_can_rollback(self):
        with self.assertRaises(DeletionSwapError):
            self.swap(_fail_at="after")
        journal=list(self.root.glob("rag-del-*.journal.json"))
        tid=journal[0].name.split("-")[2].split(".")[0]
        self.assertEqual(self.undo(tid)["state"],"LAB_ROLLBACK_COMPLETE")
        self.assertEqual(json.loads(self.cat.read_text()),self.before)

    def test_stale_revision_refused_without_journal(self):
        with self.assertRaises(ValueError):
            laboratory_swap("demo","stale",self.new,catalog_file=self.cat,public_pointer=self.pointer,
                            operator_approved=True,laboratory_mode=True)
        self.assertFalse(list(self.root.glob("rag-del-*.journal.json")))

    def test_explicit_approval_required(self):
        with self.assertRaises(PermissionError):
            laboratory_swap("demo","old",self.new,catalog_file=self.cat,public_pointer=self.pointer,
                            operator_approved=False,laboratory_mode=True)

    def test_non_temporary_catalog_denied(self):
        destination=self.root.parent.parent/"project-indexes.json"
        with self.assertRaises(DeletionSwapError):
            laboratory_swap("demo","old",self.new,catalog_file=destination,
                public_pointer=self.pointer,operator_approved=True,laboratory_mode=True)

    def test_public_pointer_change_refuses_rollback(self):
        result=self.swap()
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"altered"}))
        with self.assertRaises(DeletionSwapError):
            self.undo(result["transaction"])

    def test_modified_backup_refuses_rollback(self):
        result=self.swap()
        backups=list(self.root.glob("rag-del-*.previous.json"))
        self.assertEqual(len(backups),1)
        backups[0].write_bytes(b"modified-backup")
        with self.assertRaises(DeletionSwapError):
            self.undo(result["transaction"])

    def test_no_operational_flag_in_result(self):
        result=self.swap()
        self.assertFalse(result["operational_use_allowed"])
        self.assertFalse(result["public_pointer_updated"])

    def test_foreign_catalog_change_refuses_rollback(self):
        result=self.swap()
        data=json.loads(self.cat.read_text())
        data["projects"]["other"]["source_revision"]="unexpected"
        self.cat.write_text(json.dumps(data))
        with self.assertRaises(DeletionSwapError):
            self.undo(result["transaction"])
