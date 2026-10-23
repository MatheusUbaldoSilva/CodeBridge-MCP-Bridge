import unittest
from installer.rag_p9b_detached_shutdown_recovery_controller import run_detached_shutdown_recovery


class DetachedLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.kw=dict(installed="C:/CodeBridge",identity_manifest="id.json",
            identity_sha256="a"*64,source_commit="b"*40,
            expected_process_digest="c"*64,external=True,execute=True,
            external_interpreter="C:/External/python.exe",
            external_psutil_origin="C:/External/psutil/__init__.py",
            external_staged_lib="C:/External",
            runtime_probe=lambda **kw:{
                "state":"EXTERNAL_RUNTIME_PATHS_VERIFIED","verified":True},
            ancestry_probe=lambda **kw:{
                "state":"EXTERNAL_PROCESS_ANCESTRY_VERIFIED","verified":True},
            journal=lambda state,details:self.events.append(state),
            proof=lambda **kw:{
                "state":"DETACHED_SUPERVISOR_SHUTDOWN_PENDING",
                "artifacts_verified":True,
                "shutdown_identity_digest":"c"*64,"authorized":False},
            shutdown=lambda *a,**k:{"state":"SHUTDOWN_SIGNALS_COMPLETED",
                                    "processes_stopped":True},
            poststop=lambda *a:{"state":"POSTSTOP_OBSERVED_ONLY",
                                 "observed_stopped":True},
            restart=lambda *a:{"state":"GUI_PROCESS_RECOVERED","launched":True})
    def check(self,**overrides):
        return run_detached_shutdown_recovery(**(self.kw|overrides))
    def test_default_refuses_without_external_executor(self):
        r=self.check(external=False)
        self.assertEqual(r["reason"],"INDEPENDENT_CONTROLLER_REQUIRED")
        self.assertEqual(self.events,[])
    def test_malformed_digest_refuses_before_any_probe_or_journal(self):
        for field, value in (
            ("expected_process_digest", "z"*64),
            ("expected_process_digest", "C"*64),
            ("expected_process_digest", "a"*63),
            ("identity_sha256", "x"*64),
            ("identity_sha256", True),
        ):
            with self.subTest(field=field,value=value):
                calls=[]
                report=self.check(**{field:value},
                    runtime_probe=lambda **kw:calls.append("runtime"))
                self.assertEqual(report["reason"],
                                 "INDEPENDENT_CONTROLLER_REQUIRED")
                self.assertEqual(calls,[])
                self.assertEqual(self.events,[])

    def test_initial_journal_records_exact_release_identity(self):
        entries=[]
        result=self.check(journal=lambda state,details:
                          entries.append((state,details)))
        self.assertEqual(result["state"],"DETACHED_GUI_RESTARTED_HANDSHAKE_PENDING")
        self.assertEqual(entries[0],(
            "SHELL_DETACHED_LIFECYCLE_ARMED",{"transaction_sha256":"a"*64}))

    def test_completes_only_gui_restart_handshake_pending(self):
        r=self.check()
        self.assertEqual(r["state"],"DETACHED_GUI_RESTARTED_HANDSHAKE_PENDING")
        self.assertFalse(r["verified"])
        self.assertFalse(r["installer_authorized"])
        self.assertEqual(self.events,[
            "SHELL_DETACHED_LIFECYCLE_ARMED",
            "SHELL_DETACHED_SHUTDOWN_SIGNALED",
            "SHELL_DETACHED_POSTSTOP_VERIFIED",
            "SHELL_DETACHED_GUI_RESTARTED"])
    def test_external_runtime_must_be_verified_before_workers(self):
        calls=[]
        r=self.check(runtime_probe=lambda **kw:{
            "state":"EXTERNAL_RUNTIME_REFUSED","verified":False},
            proof=lambda **kw:calls.append("proof"))
        self.assertEqual(r["reason"],"EXTERNAL_RUNTIME_PATHS_REQUIRED")
        self.assertEqual(calls,[])
        self.assertEqual(self.events,[])

    def test_mcp_parent_process_blocks_before_journal(self):
        touched=[]
        r=self.check(ancestry_probe=lambda **kw:{
            "state":"EXTERNAL_ANCESTRY_UNVERIFIED","verified":False,
            "reason":"PROCESS_INSIDE_INSTALLED_APP"},
            proof=lambda **kw:touched.append(True))
        self.assertEqual(r["reason"],"INDEPENDENT_PROCESS_ANCESTRY_REQUIRED")
        self.assertEqual(touched,[])
        self.assertEqual(self.events,[])

    def test_parent_changes_after_arm_blocks_shutdown(self):
        calls=[]
        def drifting(**kw):
            calls.append(1)
            return {"state":"EXTERNAL_PROCESS_ANCESTRY_VERIFIED",
                    "verified":len(calls)==1}
        signals=[]
        r=self.check(ancestry_probe=drifting,
            shutdown=lambda *a,**kw:signals.append(True))
        self.assertEqual(r["reason"],"INDEPENDENT_PROCESS_ANCESTRY_CHANGED")
        self.assertEqual(len(calls),2)
        self.assertEqual(signals,[])
        self.assertIn("SHELL_DETACHED_ANCESTRY_RECHECK_FAILED",self.events)

    def test_changed_digest_prevents_first_journal_event(self):
        r=self.check(proof=lambda **kw:{"state":"DETACHED_SUPERVISOR_SHUTDOWN_PENDING",
            "artifacts_verified":True,"shutdown_identity_digest":"d"*64,
            "authorized":False})
        self.assertEqual(r["reason"],"SHUTDOWN_PLAN_OR_IDENTITY_CHANGED")
        self.assertEqual(self.events,[])
    def test_shutdown_failure_never_attempts_restart(self):
        calls=[]
        r=self.check(shutdown=lambda *a,**k:{"state":"PARTIAL_SHUTDOWN"},
                     restart=lambda *a:calls.append(1))
        self.assertEqual(r["reason"],"SHUTDOWN_FAILED")
        self.assertEqual(calls,[])
    def test_poststop_missing_prevents_restart(self):
        calls=[]
        r=self.check(poststop=lambda *a:{"state":"POSTSTOP_UNVERIFIED"},
                     restart=lambda *a:calls.append(1))
        self.assertEqual(r["reason"],"POSTSTOP_NOT_PROVEN")
        self.assertEqual(calls,[])
    def test_restart_failure_requires_review(self):
        r=self.check(restart=lambda *a:{"state":"RECOVERY_PENDING","launched":True})
        self.assertEqual(r["reason"],"RESTART_NOT_CONFIRMED")
    def test_identity_changes_after_journal_arm_never_sends_signal(self):
        evidence=[]
        signals=[]
        def drifting(**kw):
            evidence.append(1)
            return {"state":"DETACHED_SUPERVISOR_SHUTDOWN_PENDING",
                "artifacts_verified":True,"authorized":False,
                "shutdown_identity_digest":("c" if len(evidence)==1 else "d")*64}
        r=self.check(proof=drifting,
            shutdown=lambda *a,**k:signals.append(True))
        self.assertEqual(r["reason"],"PRE_SIGNAL_IDENTITY_CHANGED")
        self.assertEqual(len(evidence),2)
        self.assertEqual(signals,[])
        self.assertIn("SHELL_DETACHED_PRE_SIGNAL_RECHECK_FAILED",self.events)

    def test_journal_failure_before_shutdown_prevents_any_signal(self):
        calls=[]
        def fail(state,details):
            raise OSError("journal disk unavailable")
        result=self.check(journal=fail,
            shutdown=lambda *args,**kw:calls.append("shutdown"))
        self.assertEqual(result["reason"],"LIFECYCLE_WORKER_EXCEPTION")
        self.assertEqual(calls,[])
        self.assertFalse(result["verified"])

    def test_journal_failure_after_shutdown_requires_review(self):
        calls=[]
        def fail_second(state,details):
            calls.append(state)
            if len(calls)==2:raise OSError("disk error after stop")
        result=self.check(journal=fail_second)
        self.assertEqual(result["state"],"DETACHED_LIFECYCLE_REVIEW_REQUIRED")
        self.assertFalse(result["verified"])
        self.assertEqual(calls[0],"SHELL_DETACHED_LIFECYCLE_ARMED")

    def test_worker_exception_is_journaled(self):
        def fail(*args,**kwargs): raise OSError("synthetic")
        r=self.check(shutdown=fail)
        self.assertEqual(r["reason"],"LIFECYCLE_WORKER_EXCEPTION")
        self.assertIn("SHELL_DETACHED_LIFECYCLE_EXCEPTION",self.events)
if __name__=="__main__":unittest.main()
