from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from rag.runtime.knowledge_deletion_recovery_plan import plan_lab_recovery

class RecoveryPlanTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.catalog=self.root/"project-indexes.json"
        self.pointer=self.root/"public.json"
    @patch("rag.runtime.knowledge_deletion_recovery_plan.inspect_laboratory_transactions")
    def test_empty(self,inspect):
        inspect.return_value=[]
        result=plan_lab_recovery(self.catalog,self.pointer)
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["plans"],[])
    @patch("rag.runtime.knowledge_deletion_recovery_plan.inspect_laboratory_transactions")
    def test_interrupted_before_and_after(self,inspect):
        inspect.return_value=[
            {"transaction":"a"*32,"state":"PREPARED",
             "disposition":"CATALOG_AT_OLD_REVISION","requires_manual_review":False},
            {"transaction":"b"*32,"state":"PREPARED",
             "disposition":"CATALOG_AT_NEW_REVISION","requires_manual_review":False}]
        result=plan_lab_recovery(self.catalog,self.pointer)
        self.assertEqual(result["plans"][0]["recommended_action"],"RECONCILE_PREPARED_WITHOUT_SWITCH")
        self.assertEqual(result["plans"][1]["recommended_action"],"ROLLBACK_ELIGIBLE_AFTER_REVALIDATION")
        self.assertFalse(result["rollback_authorized"])
    @patch("rag.runtime.knowledge_deletion_recovery_plan.inspect_laboratory_transactions")
    def test_changed_pointer_never_authorizes_repair(self,inspect):
        inspect.return_value=[{"transaction":"c"*32,"state":"ACTIVE",
           "disposition":"PUBLIC_POINTER_CHANGED_MANUAL_REVIEW","requires_manual_review":True}]
        plan=plan_lab_recovery(self.catalog,self.pointer)
        self.assertEqual(plan["plans"][0]["recommended_action"],"MANUAL_INVESTIGATION_REQUIRED")
        self.assertFalse(plan["plans"][0]["automatic_repair_authorized"])
    @patch("rag.runtime.knowledge_deletion_recovery_plan.inspect_laboratory_transactions")
    def test_active_catalog_needs_decision(self,inspect):
        inspect.return_value=[{"transaction":"d"*32,"state":"ACTIVE",
           "disposition":"CATALOG_AT_NEW_REVISION","requires_manual_review":False}]
        self.assertEqual(plan_lab_recovery(self.catalog,self.pointer)["plans"][0]["recommended_action"],
                         "ACTIVE_TRANSACTION_REQUIRES_EXPLICIT_DECISION")
