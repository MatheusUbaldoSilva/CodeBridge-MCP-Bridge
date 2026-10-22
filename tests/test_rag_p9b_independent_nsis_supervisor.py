import unittest
from installer.rag_p9b_independent_nsis_supervisor import assess_independent_release

class SupervisorTests(unittest.TestCase):
    def run_check(self,*,artifacts=True,preimage=True,topology="SUPERVISOR_UPDATE_BLOCKED_RUNNING"):
        return assess_independent_release(
            installed="root",installer="installer",file_snapshot="files",
            shell_snapshot="shell",preimage="preimage",installer_sha="a"*64,
            file_snapshot_sha="b"*64,shell_snapshot_sha="c"*64,
            preimage_sha="d"*64,source_commit="e"*40,
            appdata="appdata",desktop="desktop",
            artifact_probe=lambda *args,**kwargs:{"state":"THREE_WAY_BACKUP_OBSERVED_ONLY","verified":artifacts},
            preimage_probe=lambda *args:{"state":"CRASH_PREIMAGE_VERIFIED","verified":preimage},
            process_probe=lambda *args:{"state":topology,
                                         "blockers":["GUI","MCP","ADAPTER","TUNNEL"]})
    def test_live_processes_block(self):
        r=self.run_check()
        self.assertEqual(r["reason"],"INSTALLED_STACK_STILL_RUNNING")
        self.assertFalse(r["release_authorized"])
    def test_invalid_pair_blocks(self):
        self.assertEqual(self.run_check(artifacts=False)["reason"],"THREE_WAY_ARTIFACTS_INVALID")
    def test_invalid_preimage_blocks(self):
        self.assertEqual(self.run_check(preimage=False)["reason"],"CRASH_PREIMAGE_INVALID")
    def test_absent_components_not_approval(self):
        r=self.run_check(topology="SUPERVISOR_TOPOLOGY_INCOMPLETE")
        self.assertEqual(r["state"],"INDEPENDENT_NSIS_POSTSTOP_PROOF_REQUIRED")
        self.assertFalse(r["release_authorized"])
    def test_unknown_topology_blocks(self):
        self.assertEqual(self.run_check(topology="SUPERVISOR_PREFLIGHT_UNVERIFIED")["reason"],
                         "PROCESS_TOPOLOGY_UNVERIFIED")

if __name__=="__main__":unittest.main()
