import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_three_way_backup_gate import verify_three_way


class ThreeWayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.shell=self.root/"shell.zip"
        self.shell.write_bytes(b"synthetic shell backup")
        self.sha=hashlib.sha256(self.shell.read_bytes()).hexdigest()

    def run_it(self,paired=True,shell_ok=True,digest=None):
        return verify_three_way("installer","files",self.shell,"installed",
            installer_hash="a"*64,file_snapshot_hash="b"*64,
            shell_snapshot_hash=digest or self.sha,source_commit="c"*40,
            appdata="appdata",desktop="desktop",
            pair_probe=lambda *args,**kwargs:{"paired":paired},
            shell_probe=lambda *args,**kwargs:{"verified":shell_ok,
                                               "reason":"SHELL_CHANGED"})

    def test_valid_only_observed(self):
        r=self.run_it()
        self.assertEqual(r["state"],"THREE_WAY_BACKUP_OBSERVED_ONLY")
        self.assertFalse(r["authorized"])

    def test_bad_pair_blocks(self):
        self.assertEqual(self.run_it(paired=False)["reason"],
                         "FILE_ROLLBACK_PAIR_INVALID")

    def test_shell_changed_blocks(self):
        self.assertEqual(self.run_it(shell_ok=False)["reason"],
                         "SHELL_BASELINE_CHANGED")

    def test_shell_digest_changed_blocks(self):
        self.assertEqual(self.run_it(digest="e"*64)["reason"],
                         "SHELL_SNAPSHOT_DIGEST_INVALID")


if __name__=="__main__":
    unittest.main()
