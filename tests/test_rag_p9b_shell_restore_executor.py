import unittest
from unittest.mock import Mock,patch
from installer.rag_p9b_shell_restore_executor import execute_shell_restore


PLAN={"state":"SHELL_RESTORE_PLAN_ONLY","shortcut_actions":[],"registry_actions":[]}


class ExecutorTests(unittest.TestCase):
    def run_it(self,**kw):
        args=dict(appdata="a",desktop="d",expected_sha256="a"*64,
                  stopped_verified=True,independent=True,execute=True,
                  backend=lambda p,s:{"verified":True,"registry_modified":True,
                                      "shortcuts_modified":True},
                  journal=lambda *args:None,
                  postverify=lambda *args:{"verified":True})
        args.update(kw)
        return execute_shell_restore("snapshot",**args)

    def test_default_refuses(self):
        self.assertEqual(execute_shell_restore("s",appdata="a",desktop="d",
            expected_sha256="a"*64)["reason"],"RECOVERY_GATES_MISSING")

    def test_no_backend_refuses(self):
        self.assertEqual(self.run_it(backend=None)["reason"],
                         "INDEPENDENT_BACKEND_JOURNAL_AND_POSTVERIFY_REQUIRED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_verified_backend(self,_):
        r=self.run_it()
        self.assertEqual(r["state"],"SHELL_RESTORE_VERIFIED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_backend_requires_independent_verification(self,_):
        r=self.run_it(backend=lambda *args:{"state":"SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED",
                                               "verified":False})
        self.assertEqual(r["state"],"SHELL_RESTORE_VERIFIED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_backend_application_not_sufficient(self,_):
        r=self.run_it(backend=lambda *args:{"state":"SHELL_BACKEND_APPLIED_POSTVERIFY_REQUIRED",
                                               "verified":False},
                      postverify=lambda *args:{"verified":False})
        self.assertEqual(r["reason"],"INDEPENDENT_POSTVERIFY_FAILED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_unverified_backend(self,_):
        r=self.run_it(backend=lambda *args:{"verified":False})
        self.assertEqual(r["state"],"SHELL_RESTORE_REVIEW_REQUIRED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_postverification_failed(self,_):
        r=self.run_it(postverify=lambda *args:{"verified":False})
        self.assertEqual(r["reason"],"INDEPENDENT_POSTVERIFY_FAILED")
        self.assertFalse(r["restored"])

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",return_value=PLAN)
    def test_transaction_exception(self,_):
        def fail(*args):raise OSError("injected")
        r=self.run_it(backend=fail)
        self.assertEqual(r["state"],"SHELL_RESTORE_REVIEW_REQUIRED")

    @patch("installer.rag_p9b_shell_restore_executor.build_shell_restore_plan",
           return_value={"state":"SHELL_RESTORE_PLAN_REFUSED","reason":"BAD"})
    def test_unverified_plan(self,_):
        self.assertEqual(self.run_it()["reason"],"RESTORE_PLAN_UNVERIFIED")

if __name__=="__main__":
    unittest.main()
