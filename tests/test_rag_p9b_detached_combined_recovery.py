import unittest

from installer.rag_p9b_detached_combined_recovery import recover_detached_combined


class DetachedCombinedTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.files=lambda: {"state":"DETACHED_FILES_RESTORED_SHELL_PENDING",
                            "verified":True,"shell_restore_required":True}
        self.shell=lambda: {"state":"SHELL_RESTORE_VERIFIED","restored":True}
        self.verify=lambda: {"verified":True}
        self.args=dict(file_worker=self.files,shell_worker=self.shell,
                       verify_worker=self.verify,
                       journal=lambda s,d:self.events.append(s),
                       independent=True,execute=True)

    def test_proven_order_requires_final_independent_verification(self):
        result=recover_detached_combined(**self.args)
        self.assertEqual(result["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
        self.assertTrue(result["verified"])
        self.assertFalse(result["cutover_authorized"])
        self.assertEqual(self.events,[
            "SHELL_DETACHED_COMBINED_ARMED",
            "SHELL_DETACHED_FILES_VERIFIED",
            "SHELL_DETACHED_SHELL_VERIFIED",
            "SHELL_DETACHED_COMBINED_VERIFIED"])

    def test_replay_after_shell_crash_with_durable_journal(self):
        import tempfile
        from pathlib import Path
        from installer.rag_p9b_rollback_journal import RollbackJournal,read_journal
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"transaction.jsonl"
            first=RollbackJournal(path)
            calls=[]
            def crash():
                calls.append("shell")
                raise OSError("injected shell interruption")
            refused=recover_detached_combined(**(self.args|{
                "journal":first,"shell_worker":crash}))
            self.assertEqual(refused["state"],"DETACHED_COMBINED_REVIEW_REQUIRED")
            self.assertEqual(refused["failed_stage"],"SHELL")
            self.assertEqual(read_journal(path)["last_state"],
                             "SHELL_DETACHED_COMBINED_EXCEPTION")
            resumed=RollbackJournal.resume(path)
            result=recover_detached_combined(**(self.args|{"journal":resumed}))
            self.assertEqual(result["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
            self.assertEqual(read_journal(path)["last_state"],
                             "SHELL_DETACHED_COMBINED_VERIFIED")
            with self.assertRaises(ValueError):
                RollbackJournal.resume(path)

    def test_production_refuses_without_verified_identity(self):
        r=recover_detached_combined(**(self.args|{"production":True}))
        self.assertEqual(r["reason"],"BOUND_TRANSACTION_IDENTITY_REQUIRED")
        self.assertEqual(self.events,[])

    def test_production_refuses_invalid_identity(self):
        r=recover_detached_combined(**(self.args|{
            "production":True,"identity_manifest":"dummy",
            "identity_sha256":"bad","installed":"C:/CodeBridge",
            "source_commit":"a"*40,
            "identity_gate":lambda **kw:{"state":"DETACHED_COMBINED_IDENTITY_REFUSED"}}))
        self.assertEqual(r["reason"],"BOUND_TRANSACTION_IDENTITY_REQUIRED")
        self.assertEqual(self.events,[])

    def test_production_validates_identity_before_workers(self):
        observed=[]
        def gate(**kw):
            observed.append(kw)
            return {"state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                    "identity_verified":True,"artifacts_checked":4,
                    "cutover_authorized":False}
        r=recover_detached_combined(**(self.args|{
            "production":True,"identity_manifest":"fixture",
            "identity_sha256":"a"*64,"installed":"C:/CodeBridge",
            "source_commit":"b"*40,"identity_gate":gate,
            "poststop_probe":lambda *_:{
                "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True}}))
        self.assertEqual(r["state"],"DETACHED_COMBINED_RESTORE_VERIFIED")
        self.assertFalse(r["cutover_authorized"])
        self.assertEqual(observed[0]["expected_source_commit"],"b"*40)

    def test_production_refuses_running_codebridge_even_with_valid_identity(self):
        r=recover_detached_combined(**(self.args|{
            "production":True,"identity_manifest":"fixture",
            "identity_sha256":"a"*64,"installed":"C:/CodeBridge",
            "source_commit":"b"*40,
            "identity_gate":lambda **kw:{
                "state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                "identity_verified":True,"artifacts_checked":4,
                "cutover_authorized":False},
            "poststop_probe":lambda *_:{
                "state":"POSTSTOP_UNVERIFIED","observed_stopped":False}}))
        self.assertEqual(r["reason"],"INDEPENDENT_POSTSTOP_REQUIRED")
        self.assertEqual(self.events,[])

    def test_production_rechecks_processes_before_shell(self):
        snapshots=[]
        shell_calls=[]
        def poststop(*args):
            snapshots.append(len(snapshots))
            return {"state":"POSTSTOP_OBSERVED_ONLY",
                    "observed_stopped":len(snapshots)==1}
        r=recover_detached_combined(**(self.args|{
            "production":True,"identity_manifest":"fixture",
            "identity_sha256":"a"*64,"installed":"C:/CodeBridge",
            "source_commit":"b"*40,
            "identity_gate":lambda **kw:{
                "state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                "identity_verified":True,"artifacts_checked":4,
                "cutover_authorized":False},
            "poststop_probe":poststop,
            "shell_worker":lambda:shell_calls.append(1)}))
        self.assertEqual(r["reason"],"POSTSTOP_LOST_BEFORE_SHELL")
        self.assertEqual(len(snapshots),2)
        self.assertEqual(shell_calls,[])
        self.assertIn("SHELL_DETACHED_POSTSTOP_RECHECK_FAILED",self.events)

    def test_production_rechecks_processes_before_final_postverify(self):
        snapshots=[]
        verifier_calls=[]
        def probe(*args):
            snapshots.append(1)
            return {"state":"POSTSTOP_OBSERVED_ONLY",
                    "observed_stopped":len(snapshots)<3}
        r=recover_detached_combined(**(self.args|{
            "production":True,"identity_manifest":"fixture",
            "identity_sha256":"a"*64,"installed":"C:/CodeBridge",
            "source_commit":"b"*40,
            "identity_gate":lambda **kw:{
                "state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                "identity_verified":True,"artifacts_checked":4,
                "cutover_authorized":False},
            "poststop_probe":probe,
            "verify_worker":lambda:verifier_calls.append(1)}))
        self.assertEqual(r["reason"],"POSTSTOP_LOST_BEFORE_POSTVERIFY")
        self.assertEqual(len(snapshots),3)
        self.assertEqual(verifier_calls,[])
        self.assertIn("SHELL_DETACHED_FINAL_POSTSTOP_FAILED",self.events)

    def test_execute_off_refuses_without_worker_calls(self):
        self.assertEqual(recover_detached_combined(**(self.args|{
            "execute":False}))["reason"],"INDEPENDENT_WORKERS_REQUIRED")
        self.assertEqual(self.events,[])

    def test_file_failure_never_runs_shell(self):
        invoked=[]
        result=recover_detached_combined(**(self.args|{
            "file_worker":lambda: {"verified":False},
            "shell_worker":lambda:invoked.append("shell")}))
        self.assertEqual(result["reason"],"FILES_NOT_VERIFIED")
        self.assertEqual(invoked,[])

    def test_shell_failure_never_verifies_final(self):
        invoked=[]
        result=recover_detached_combined(**(self.args|{
            "shell_worker":lambda:{"state":"SHELL_RESTORE_REVIEW_REQUIRED"},
            "verify_worker":lambda:invoked.append("verify")}))
        self.assertEqual(result["reason"],"SHELL_NOT_VERIFIED")
        self.assertEqual(invoked,[])

    def test_postverify_failure_never_reports_success(self):
        result=recover_detached_combined(**(self.args|{
            "verify_worker":lambda:{"verified":False}}))
        self.assertEqual(result["reason"],"INDEPENDENT_POSTVERIFY_FAILED")
        self.assertFalse(result["verified"])

    def test_worker_crash_requires_review(self):
        def crash():
            raise OSError("synthetic interruption")
        result=recover_detached_combined(**(self.args|{"shell_worker":crash}))
        self.assertEqual(result["state"],"DETACHED_COMBINED_REVIEW_REQUIRED")
        self.assertEqual(result["failed_stage"],"SHELL")
        self.assertIn("SHELL_DETACHED_COMBINED_EXCEPTION",self.events)

    def test_journal_failure_is_not_success(self):
        def fail(state,detail):
            raise OSError("journal failure")
        result=recover_detached_combined(**(self.args|{"journal":fail}))
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason"],"WORKER_OR_JOURNAL_EXCEPTION")


if __name__=="__main__":
    unittest.main()
