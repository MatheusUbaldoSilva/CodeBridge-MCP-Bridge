import unittest
from installer.rag_p9b_cutover_decision import decide_cutover


class CutoverTests(unittest.TestCase):
    def check(self, *, pair=True, process="NO_RUNNING_CODEBRIDGE",
              generation="v1_delta_1ae1d01ea84f4e", external=True,
              scratch=True):
        return decide_cutover(installer="exe",snapshot="zip",installed="root",
               installer_sha="a"*64,snapshot_sha="b"*64,source_commit="c"*40,
               generation=generation,independent_channel_ready=external,
               scratch_restore_proven=scratch,
               pair_check=lambda *a,**k:{"paired":pair},
               process_check=lambda *a,**k:{"state":process,
                                            "blockers":["CODEBRIDGE_GUI_RUNNING"]})

    def test_valid_only_observed(self):
        r=self.check()
        self.assertEqual(r["state"],"P9B_PREFLIGHT_OBSERVED_ONLY")
        self.assertFalse(r["operator_execution_authorized"])

    def test_live_codebridge_blocks(self):
        r=self.check(process="UPDATE_PROCESS_BLOCKED")
        self.assertEqual(r["reason"],"NSIS_PROCESS_GUARD_BLOCKED")

    def test_unverified_pair_blocks(self):
        self.assertEqual(self.check(pair=False)["reason"],
                         "INSTALLER_BACKUP_PAIR_UNVERIFIED")

    def test_generation_changed_blocks(self):
        self.assertEqual(self.check(generation="other")["reason"],
                         "RAG_GENERATION_CHANGED")

    def test_external_absent_blocks(self):
        self.assertEqual(self.check(external=False)["reason"],
                         "RECOVERY_PREREQUISITE_MISSING")

    def test_rollback_absent_blocks(self):
        self.assertEqual(self.check(scratch=False)["reason"],
                         "RECOVERY_PREREQUISITE_MISSING")


if __name__=="__main__":
    unittest.main()
