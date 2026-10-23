import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_scheduled_supervisor_readonly import inspect_scheduled_supervisor
from installer.rag_p9b_transaction_identity import NAMES,write_identity,digest


class ScheduledAttestationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.install=self.root/"installed"
        self.install.mkdir()
        self.stage=self.root/"stage"
        self.stage.mkdir()
        (self.stage/"external_supervisor_lib").mkdir()
        artifacts={}
        for name in NAMES:
            file=self.stage/(name+".bin")
            file.write_bytes(name.encode())
            artifacts[name]=file
        self.commit="b"*40
        self.manifest=self.stage/"identity.json"
        write_identity(self.manifest,artifacts=artifacts,
                       installed=self.install,source_commit=self.commit)
        self.kw=dict(installed=self.install,stage=self.stage,identity=self.manifest,
            identity_sha=digest(self.manifest),expected_commit=self.commit,
            interpreter=self.root/"python.exe",psutil_origin=self.root/"psutil.py",
            runtime_probe=lambda **kw:{"state":"EXTERNAL_RUNTIME_PATHS_VERIFIED","verified":True},
            ancestry_probe=lambda **kw:{"state":"EXTERNAL_PROCESS_ANCESTRY_VERIFIED","verified":True},
            shutdown_probe=lambda *a:{"state":"SHUTDOWN_PLAN_ONLY",
                "identity_digest":"c"*64})
    def test_attested_is_never_authorized(self):
        r=inspect_scheduled_supervisor(**self.kw)
        self.assertEqual(r["state"],"SCHEDULED_SUPERVISOR_READONLY_ATTESTED")
        self.assertFalse(r["authorized"])
        self.assertFalse(r["shutdown_signals_sent"])
    def test_shutdown_topology_must_be_verified(self):
        r=inspect_scheduled_supervisor(**(self.kw|{
            "shutdown_probe":lambda *a:{"state":"SHUTDOWN_PLAN_REFUSED"}}))
        self.assertEqual(r["reason"],"SHUTDOWN_TOPOLOGY_NOT_VERIFIED")
        self.assertFalse(r["authorized"])
        self.assertFalse(r["shutdown_signals_sent"])

    def test_no_ancestry_refused(self):
        r=inspect_scheduled_supervisor(**(self.kw|{
            "ancestry_probe":lambda **kw:{"verified":False}}))
        self.assertEqual(r["reason"],"EXTERNAL_ANCESTRY_REQUIRED")
    def test_bad_identity_refused(self):
        r=inspect_scheduled_supervisor(**(self.kw|{
            "identity_sha":"f"*64}))
        self.assertEqual(r["reason"],"IDENTITY_DIGEST_MISMATCH")
    def test_wrong_source_commit_refused(self):
        r=inspect_scheduled_supervisor(**(self.kw|{
            "expected_commit":"a"*40}))
        self.assertEqual(r["reason"],"TRANSACTION_IDENTITY_INVALID")
    def test_stage_outside_identity_refused(self):
        other=self.root/"other.json"
        other.write_bytes(self.manifest.read_bytes())
        r=inspect_scheduled_supervisor(**(self.kw|{"identity":other}))
        self.assertEqual(r["reason"],"STAGING_SCOPE_INVALID")


if __name__=="__main__":unittest.main()
