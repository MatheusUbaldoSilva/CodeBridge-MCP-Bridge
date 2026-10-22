import unittest
from unittest.mock import Mock
from installer.rag_p9b_external_cutover_rehearsal import rehearse_cutover


def plan(_):
    return dict(state="SHUTDOWN_PLAN_ONLY",identity_digest="abc")


class CutoverTests(unittest.TestCase):
    def test_default_is_inert(self):
        stop=Mock()
        r=rehearse_cutover(".",expected_digest="abc",stop=stop)
        self.assertEqual(r["reason"],"EXTERNAL_EXECUTION_REQUIRED")
        stop.assert_not_called()

    def test_wrong_digest_blocks(self):
        stop=Mock()
        r=rehearse_cutover(".",expected_digest="bad",external_channel=True,
                           execute=True,stop=stop,plan=plan)
        self.assertEqual(r["reason"],"IDENTITY_PLAN_CHANGED")
        stop.assert_not_called()

    def test_failed_stop_not_reported_as_recovered(self):
        recover=Mock()
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(state="SHUTDOWN_REFUSED",
                                                    reason="GUI_WM_CLOSE_FAILED",
                                                    processes_stopped=False),
                           recover=recover)
        self.assertEqual(r["state"],"CUTOVER_STOP_FAILED")
        recover.assert_not_called()

    def test_partial_shutdown_attempts_gui_recovery(self):
        recover=Mock(return_value=dict(state="GUI_PROCESS_RECOVERED"))
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(state="PARTIAL_SHUTDOWN",
                                                    reason="GRACEFUL_TIMEOUT",
                                                    processes_stopped=False),
                           recover=recover)
        self.assertEqual(r["state"],"CUTOVER_PARTIAL_SHUTDOWN_RECOVERY_ATTEMPTED")
        self.assertFalse(r["mcp_handshake_verified"])
        recover.assert_called_once()

    def test_poststop_failure_still_attempts_gui_recovery(self):
        recover=Mock(return_value=dict(state="GUI_PROCESS_RECOVERED"))
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=lambda root:dict(observed_stopped=False,
                                                   reason="GUARD_BLOCKED"),
                           recover=recover)
        self.assertEqual(r["state"],"CUTOVER_POSTSTOP_UNVERIFIED")
        recover.assert_called_once()

    def test_recovered_gui_does_not_claim_mcp_handshake(self):
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=lambda root:dict(observed_stopped=True),
                           recover=lambda root:dict(state="GUI_PROCESS_RECOVERED"),
                           local_health=lambda root:dict(verified=False,
                                                         state="LOCAL_MCP_NOT_READY"))
        self.assertEqual(r["state"],"CUTOVER_MCP_LOCAL_UNVERIFIED")
        self.assertFalse(r["mcp_handshake_verified"])

    def test_poststop_probe_exception_still_relaunches(self):
        recover=Mock(return_value=dict(state="GUI_PROCESS_RECOVERED"))
        def explode(root): raise RuntimeError("synthetic")
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=explode,recover=recover)
        self.assertEqual(r["state"],"CUTOVER_POSTSTOP_UNVERIFIED")
        recover.assert_called_once()

    def test_recovery_exception_not_reported_success(self):
        def explode(root): raise RuntimeError("synthetic")
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=lambda root:dict(observed_stopped=True),
                           recover=explode)
        self.assertEqual(r["state"],"CUTOVER_RECOVERY_UNVERIFIED")

    def test_local_health_ready_still_requires_public_handshake(self):
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=lambda root:dict(observed_stopped=True),
                           recover=lambda root:dict(state="GUI_PROCESS_RECOVERED"),
                           local_health=lambda root:dict(verified=True,
                                                         state="LOCAL_ADAPTER_AND_MCP_READY"))
        self.assertEqual(r["state"],"CUTOVER_LOCAL_STACK_RECOVERED")
        self.assertFalse(r["mcp_handshake_verified"])

    def test_failed_recovery_remains_unverified(self):
        r=rehearse_cutover(".",expected_digest="abc",external_channel=True,
                           execute=True,plan=plan,
                           stop=lambda *a,**kw:dict(processes_stopped=True),
                           verify=lambda root:dict(observed_stopped=True),
                           recover=lambda root:dict(state="RECOVERY_PENDING"))
        self.assertEqual(r["state"],"CUTOVER_RECOVERY_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
