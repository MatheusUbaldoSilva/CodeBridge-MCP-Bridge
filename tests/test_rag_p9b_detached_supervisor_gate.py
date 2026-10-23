import unittest
from installer.rag_p9b_detached_supervisor_gate import assess_detached_supervisor

class SupervisorGateTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.kw=dict(installed="C:/CodeBridge",identity_manifest="id.json",
            identity_sha256="a"*64,source_commit="b"*40,external_runtime=True,
            identity_probe=lambda **a:self.events.append("identity") or {
                "state":"DETACHED_IDENTITY_OBSERVED_ONLY",
                "identity_verified":True,"artifacts_checked":4},
            ancestry_probe=lambda **kw:{
                "state":"EXTERNAL_PROCESS_ANCESTRY_VERIFIED","verified":True},
            shutdown_probe=lambda *a:self.events.append("shutdown") or {
                "state":"SHUTDOWN_PLAN_ONLY","identity_digest":"f"*64},
            stopped_probe=lambda *a:self.events.append("poststop") or {
                "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
    def test_cli_never_returns_authorized_exit_code(self):
        from unittest.mock import patch
        from installer.rag_p9b_detached_supervisor_gate import main
        import io
        from contextlib import redirect_stdout
        capture=io.StringIO()
        with patch("installer.rag_p9b_detached_supervisor_gate.assess_detached_supervisor",
                   return_value={"state":"DETACHED_SUPERVISOR_POSTSTOP_OBSERVED",
                                 "authorized":False}):
            with redirect_stdout(capture):
                code=main(["--installed","C:/CodeBridge","--identity","x",
                           "--identity-sha","a"*64,"--source-commit","b"*40])
        self.assertEqual(code,2)
        self.assertIn('"authorized": false',capture.getvalue())

    def test_no_external_runtime_does_not_start(self):
        r=assess_detached_supervisor(**(self.kw|{"external_runtime":False}))
        self.assertEqual(r["reason"],"EXTERNAL_RUNTIME_REQUIRED")
        self.assertEqual(self.events,[])
    def test_gui_parented_executor_denied_even_with_valid_identity(self):
        r=assess_detached_supervisor(**(self.kw|{
            "ancestry_probe":lambda **kw:{
                "state":"EXTERNAL_ANCESTRY_UNVERIFIED",
                "reason":"PROCESS_INSIDE_INSTALLED_APP","verified":False}}))
        self.assertEqual(r["reason"],"EXTERNAL_ANCESTRY_REQUIRED")
        self.assertEqual(self.events,["identity"])
        self.assertFalse(r["authorized"])

    def test_shutdown_plan_never_authorizes_mutation(self):
        r=assess_detached_supervisor(**self.kw)
        self.assertEqual(r["state"],"DETACHED_SUPERVISOR_SHUTDOWN_PENDING")
        self.assertFalse(r["authorized"])
        self.assertFalse(r["shutdown_signals_sent"])
        self.assertEqual(self.events,["identity","shutdown"])
    def test_bad_identity_refused_without_shutdown(self):
        r=assess_detached_supervisor(**(self.kw|{
            "identity_probe":lambda **a:{"verified":False}}))
        self.assertEqual(r["reason"],"BOUND_IDENTITY_INVALID")
        self.assertEqual(self.events,[])
    def test_false_poststop_refused(self):
        r=assess_detached_supervisor(**(self.kw|{
            "shutdown_probe":lambda *a:{"state":"SHUTDOWN_PLAN_REFUSED"},
            "stopped_probe":lambda *a:{"state":"POSTSTOP_UNVERIFIED"}}))
        self.assertEqual(r["reason"],"INDEPENDENT_STOPPED_PROOF_MISSING")
    def test_poststop_observation_still_not_authorization(self):
        r=assess_detached_supervisor(**(self.kw|{
            "shutdown_probe":lambda *a:{"state":"SHUTDOWN_PLAN_REFUSED"}}))
        self.assertEqual(r["state"],"DETACHED_SUPERVISOR_POSTSTOP_OBSERVED")
        self.assertFalse(r["authorized"])
        self.assertFalse(r["installer_executed"])
if __name__=="__main__":unittest.main()
