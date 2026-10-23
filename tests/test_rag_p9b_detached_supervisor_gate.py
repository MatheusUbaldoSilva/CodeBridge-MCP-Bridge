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
            shutdown_probe=lambda *a:self.events.append("shutdown") or {
                "state":"SHUTDOWN_PLAN_ONLY","identity_digest":"f"*64},
            stopped_probe=lambda *a:self.events.append("poststop") or {
                "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
    def test_no_external_runtime_does_not_start(self):
        r=assess_detached_supervisor(**(self.kw|{"external_runtime":False}))
        self.assertEqual(r["reason"],"EXTERNAL_RUNTIME_REQUIRED")
        self.assertEqual(self.events,[])
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
