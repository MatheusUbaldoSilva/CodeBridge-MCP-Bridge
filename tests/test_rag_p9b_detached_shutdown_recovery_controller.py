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
    def test_worker_exception_is_journaled(self):
        def fail(*args,**kwargs): raise OSError("synthetic")
        r=self.check(shutdown=fail)
        self.assertEqual(r["reason"],"LIFECYCLE_WORKER_EXCEPTION")
        self.assertIn("SHELL_DETACHED_LIFECYCLE_EXCEPTION",self.events)
if __name__=="__main__":unittest.main()
