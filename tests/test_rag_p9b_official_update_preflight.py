import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.rag_p9b_official_update_preflight import assess_p9b_official_update


class OfficialUpdateGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.installer=root/"preview.exe"
        self.installer.write_bytes(b"MZclean")
        self.sha=hashlib.sha256(b"MZclean").hexdigest()
        self.params=dict(
            installer=self.installer,installed=root/"CodeBridge",
            snapshot=root/"rollback.zip",
            expected_installer_sha256=self.sha,
            mcp_process_running=False,
            codebridge_gui_running=False,
            independent_recovery_online=True,
            scratch_restore_proven=True,
            public_generation="v1_delta_1ae1d01ea84f4e",
            journal_present=False,
        )

    def assess(self, **override):
        kwargs={**self.params, **override}
        with patch(
            "installer.rag_p9b_official_update_preflight.verify_installer_rollback_snapshot",
            return_value={"verified":True,"installer_sha256":self.sha},
        ), patch(
            "installer.rag_p9b_official_update_preflight.inspect_installer_snapshot_baseline",
            return_value={"matches":True},
        ):
            return assess_p9b_official_update(**kwargs)

    def test_all_inputs_are_still_observations_not_execution_authorization(self):
        report=self.assess()
        self.assertEqual(report["state"],"MAINTENANCE_PREFLIGHT_OBSERVED_ONLY")
        self.assertEqual(report["blockers"],[])
        self.assertFalse(report["operator_execution_authorized"])
        self.assertFalse(report["mcp_restarted"])

    def test_running_mcp_or_gui_blocks(self):
        report=self.assess(mcp_process_running=True,codebridge_gui_running=True)
        self.assertIn("ACTIVE_MCP_MUST_SHUT_DOWN",report["blockers"])
        self.assertIn("ACTIVE_CODEBRIDGE_GUI_MUST_SHUT_DOWN",report["blockers"])

    def test_missing_recovery_channel_blocks(self):
        report=self.assess(independent_recovery_online=False,
                           scratch_restore_proven=False)
        self.assertIn("INDEPENDENT_RECOVERY_CHANNEL_NOT_VERIFIED",report["blockers"])
        self.assertIn("INDEPENDENT_RESTORE_NOT_REHEARSED",report["blockers"])

    def test_pointer_change_or_journal_blocks(self):
        report=self.assess(public_generation="legacy",journal_present=True)
        self.assertIn("PUBLIC_RAG_GENERATION_CHANGED",report["blockers"])
        self.assertIn("PUBLIC_GENERATION_TRANSITION_PENDING",report["blockers"])

    def test_modified_installer_hash_blocks(self):
        report=self.assess(expected_installer_sha256="0"*64)
        self.assertIn("CLEAN_INSTALLER_HASH_NOT_VERIFIED",report["blockers"])
        self.assertIn("FULL_INSTALLER_ROLLBACK_SNAPSHOT_UNVERIFIED",report["blockers"])


if __name__=="__main__":
    unittest.main()
