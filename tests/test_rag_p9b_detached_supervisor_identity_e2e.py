import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_transaction_identity import NAMES,write_identity
from installer.rag_p9b_detached_supervisor_gate import assess_detached_supervisor

class DetachedSupervisorIdentityIntegration(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.installed=self.root/"installed"
        self.installed.mkdir()
        files={}
        for name in NAMES:
            path=self.root/(name+".bin")
            path.write_bytes(name.encode())
            files[name]=path
        self.files=files
        self.identity=self.root/"identity.json"
        self.commit="c"*40
        result=write_identity(self.identity,artifacts=files,
                              installed=self.installed,source_commit=self.commit)
        assert result["written"]
        self.digest=result["manifest_sha256"]
        self.calls=[]
        self.args=dict(installed=self.installed,identity_manifest=self.identity,
            identity_sha256=self.digest,source_commit=self.commit,external_runtime=True,
            shutdown_probe=lambda *a:self.calls.append("plan") or {
                "state":"SHUTDOWN_PLAN_ONLY","identity_digest":"a"*64},
            stopped_probe=lambda *a:self.calls.append("poststop") or {
                "state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True})
    def test_verified_identity_then_shutdown_plan(self):
        r=assess_detached_supervisor(**self.args)
        self.assertEqual(r["state"],"DETACHED_SUPERVISOR_SHUTDOWN_PENDING")
        self.assertEqual(self.calls,["plan"])
        self.assertFalse(r["authorized"])
    def test_tamper_before_shutdown_plan_refused(self):
        self.files["installer"].write_bytes(b"changed")
        r=assess_detached_supervisor(**self.args)
        self.assertEqual(r["reason"],"BOUND_IDENTITY_INVALID")
        self.assertEqual(self.calls,[])
    def test_wrong_commit_before_shutdown_plan_refused(self):
        r=assess_detached_supervisor(**(self.args|{"source_commit":"b"*40}))
        self.assertEqual(r["reason"],"BOUND_IDENTITY_INVALID")
        self.assertEqual(self.calls,[])
    def test_stopped_but_mutating_executor_missing_is_not_approval(self):
        r=assess_detached_supervisor(**(self.args|{
            "shutdown_probe":lambda *a:{"state":"SHUTDOWN_PLAN_REFUSED"}}))
        self.assertEqual(r["state"],"DETACHED_SUPERVISOR_POSTSTOP_OBSERVED")
        self.assertFalse(r["authorized"])
if __name__=="__main__": unittest.main()
