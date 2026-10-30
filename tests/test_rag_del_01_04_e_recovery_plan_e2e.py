import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap,DeletionSwapError
from rag.runtime.knowledge_deletion_recovery_plan import plan_lab_recovery

class RecoveryPlanE2ETests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.cat=self.root/"project-indexes.json"
        self.pointer=self.root/"active-generation.json"
        self.cat.write_text(json.dumps({"schema_version":1,"projects":{
            "demo":{"project_id":"demo","enabled":True,"source_revision":"old",
                    "generation_directory":"old"}}}))
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"public"}))
        self.candidate={"project_id":"demo","enabled":True,"source_revision":"new",
                        "generation_directory":"new"}
    def switch(self,fail_at=None):
        return laboratory_swap("demo","old",self.candidate,
          catalog_file=self.cat,public_pointer=self.pointer,
          operator_approved=True,laboratory_mode=True,_fail_at=fail_at)
    def plan(self):
        return plan_lab_recovery(self.cat,self.pointer)
    def test_crash_before_switch_is_read_only(self):
        with self.assertRaises(DeletionSwapError):self.switch("before")
        before=self.cat.read_bytes()
        result=self.plan()
        self.assertEqual(result["plans"][0]["recommended_action"],"RECONCILE_PREPARED_WITHOUT_SWITCH")
        self.assertEqual(self.cat.read_bytes(),before)
        self.assertFalse(result["writes_performed"])
    def test_crash_after_switch_is_read_only(self):
        with self.assertRaises(DeletionSwapError):self.switch("after")
        before=self.cat.read_bytes()
        result=self.plan()
        self.assertEqual(result["plans"][0]["recommended_action"],"ROLLBACK_ELIGIBLE_AFTER_REVALIDATION")
        self.assertEqual(self.cat.read_bytes(),before)
        self.assertFalse(result["rollback_authorized"])
    def test_external_pointer_change_is_manual(self):
        self.switch()
        self.pointer.write_text(json.dumps({"schema_version":1,"generation":"changed"}))
        self.assertEqual(self.plan()["plans"][0]["recommended_action"],"MANUAL_INVESTIGATION_REQUIRED")
