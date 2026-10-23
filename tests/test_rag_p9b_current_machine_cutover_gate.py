import tempfile,unittest
from pathlib import Path
from installer.rag_p9b_current_machine_cutover_gate import assess

class SameMachineGateTests(unittest.TestCase):
    def test_missing_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=assess(identity=Path(tmp)/"nonexistent.json",
                       identity_sha="0"*64,installed=tmp,worktree=tmp)
            self.assertEqual(out["reason"],"TRANSACTION_IDENTITY_INVALID")
            self.assertFalse(out["authorized"])
    def test_malformed_identity_sha_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=assess(identity=Path(tmp)/"identity.json",
                       identity_sha="not-a-hash",installed=tmp,worktree=tmp)
            self.assertEqual(out["reason"],"TRANSACTION_IDENTITY_INVALID")
    def test_real_signed_candidate_checks_live_machine_and_blocks_running(self):
        import os
        base=Path(os.environ.get("LOCALAPPDATA",""))/"CodeBridge-MCP-Bridge"/"release_staging"/"P9B_HEAD_CANDIDATE_f45880511c"
        manifest=base/"P9B_HEAD_TRANSACTION_IDENTITY.json"
        if not manifest.is_file():
            self.skipTest("Candidate only staged on development workstation")
        installed=Path(os.environ["LOCALAPPDATA"])/"Programs"/"CodeBridge"
        r=assess(identity=manifest,identity_sha="6a2d32f0c4264b8dfe54b0c25e342d8cd1f94d594cdc9d98908380f0133ba9dc",
            installed=installed,worktree=Path.cwd(),appdata=Path(os.environ["APPDATA"]),
            desktop=Path.home()/"Desktop")
        self.assertFalse(r["authorized"])
        self.assertEqual(r["reason"],"PROCESSES_NOT_EXTERNALLY_STOPPED")
        self.assertFalse(r["production_modified"])
if __name__=="__main__":unittest.main()
