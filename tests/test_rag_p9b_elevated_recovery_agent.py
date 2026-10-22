import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from installer.rag_p9b_elevated_recovery_agent import run_agent


class AgentTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.journal=self.root/"journal.json"
        self.plan=lambda _: {"state":"SHUTDOWN_PLAN_ONLY",
                              "identity_digest":"expected"}

    def run_agent(self,**kwargs):
        kwargs.setdefault("elevated_check",lambda:True)
        return run_agent(self.root,digest="expected",journal=self.journal,
                         **kwargs)

    def test_default_denies_mutation(self):
        stop=Mock()
        result=self.run_agent(stop=stop)
        self.assertEqual(result["state"],"AGENT_DRY_RUN_ONLY")
        stop.assert_not_called()

    def test_denied_integrity_aborts_before_stop(self):
        stop=Mock()
        r=self.run_agent(execute=True,external_ready=True,
                         elevated_check=lambda:False,stop=stop)
        self.assertEqual(r["reason"],"ELEVATED_INTEGRITY_REQUIRED")
        stop.assert_not_called()

    def test_unhandled_exception_after_arming_still_attempts_recovery(self):
        recover=Mock(return_value={"state":"GUI_ALREADY_RUNNING"})
        def exploded(*a,**k):raise RuntimeError("after signal")
        r=self.run_agent(execute=True,external_ready=True,plan=self.plan,
                         stop=exploded,recover=recover)
        self.assertEqual(r["state"],"AGENT_EXCEPTION_RECOVERY_ATTEMPTED")
        recover.assert_called_once()

    def test_plan_revalidation_refuses(self):
        stop=Mock()
        result=self.run_agent(execute=True,external_ready=True,
                              plan=lambda _:{"state":"SHUTDOWN_PLAN_ONLY",
                                             "identity_digest":"different"},stop=stop)
        self.assertEqual(result["state"],"AGENT_REFUSED")
        stop.assert_not_called()

    def test_stop_refusal_does_not_launch(self):
        recover=Mock()
        result=self.run_agent(execute=True,external_ready=True,plan=self.plan,
            stop=lambda *a,**k:{"state":"SHUTDOWN_REFUSED",
                                 "reason":"WIN32_ACCESS_DENIED"},
            recover=recover)
        self.assertEqual(result["state"],"AGENT_STOP_REFUSED")
        recover.assert_not_called()

    def test_full_path_attempts_recovery_and_health(self):
        recover=Mock(return_value={"state":"GUI_PROCESS_RECOVERED","pid":22})
        verify=Mock(return_value={"state":"POSTSTOP_OBSERVED_ONLY",
                                  "observed_stopped":True})
        result=self.run_agent(execute=True,external_ready=True,plan=self.plan,
            stop=lambda *a,**k:{"state":"SHUTDOWN_SIGNALS_COMPLETED",
                                 "processes_stopped":True},
            verify=verify,recover=recover,
            health=lambda *_:{"verified":True,"state":"ONLINE"})
        self.assertEqual(result["state"],"LOCAL_MCP_RECOVERED_PUBLIC_RECHECK_REQUIRED")
        self.assertFalse(result["public_handshake_verified"])
        recover.assert_called_once()

    def test_partial_stop_recovers(self):
        recover=Mock(return_value={"state":"GUI_PROCESS_RECOVERED"})
        result=self.run_agent(execute=True,external_ready=True,plan=self.plan,
            stop=lambda *a,**k:{"state":"PARTIAL_SHUTDOWN",
                                 "processes_stopped":False},
            recover=recover,health=lambda *_:{"verified":True})
        self.assertEqual(result["state"],"LOCAL_MCP_RECOVERED_PUBLIC_RECHECK_REQUIRED")
        recover.assert_called_once()

    def test_health_timeout_fails_closed(self):
        result=self.run_agent(execute=True,external_ready=True,plan=self.plan,
            stop=lambda *a,**k:{"processes_stopped":True},
            verify=lambda *_:{"state":"POSTSTOP_OBSERVED_ONLY",
                              "observed_stopped":True},
            recover=lambda *_:{"state":"GUI_PROCESS_RECOVERED"},
            health=lambda *_:{"verified":False},sleep=lambda _:None)
        self.assertEqual(result["state"],"LOCAL_MCP_RECOVERY_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
