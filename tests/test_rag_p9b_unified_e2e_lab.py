import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

REPO=Path(__file__).resolve().parents[1]
CODE=("import sys;sys.path.insert(0,sys.argv[1]);"
      "from installer.rag_p9b_unified_e2e_lab import main;"
      "sys.argv=[sys.argv[0]]+sys.argv[2:];raise SystemExit(main())")

class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.lab=base/"lab"
        self.installed=base/"reference"
        self.installed.mkdir()
        self.snapshot=base/"baseline.zip"
        import hashlib
        payload=b"original"
        with ZipFile(self.snapshot,"w") as z:
            z.writestr("manifest.json",json.dumps({
                "targets":["pkg/old.py","pkg/new.py"],
                "existing":{"pkg/old.py":{"bytes":len(payload),
                           "sha256":hashlib.sha256(payload).hexdigest()}}}))
            z.writestr("old/pkg/old.py",payload)

    def call(self,action):
        return subprocess.run([sys.executable,"-c",CODE,str(REPO),
                               action,str(self.lab),str(self.snapshot),str(self.installed)],
                              text=True,capture_output=True,timeout=20)

    def test_unified_recovery_after_child_killed(self):
        from unittest.mock import patch
        from installer.rag_p9b_unified_e2e_lab import prepare
        with patch("installer.rag_p9b_unified_e2e_lab.verify_installer_rollback_snapshot",
                   return_value={"verified":True}):
            result=prepare(self.lab,self.snapshot,self.installed)
        self.assertEqual(result["state"],"UNIFIED_LAB_READY")
        killed=self.call("interrupt")
        self.assertEqual(killed.returncode,83,killed.stderr)
        resumed=self.call("recover")
        self.assertEqual(resumed.returncode,0,resumed.stderr)
        evidence=json.loads(resumed.stdout)
        self.assertEqual(evidence["state"],"UNIFIED_LAB_RECOVERED")
        self.assertEqual(evidence["old_files_checked"],1)
        self.assertEqual(evidence["new_targets_removed"],1)
        self.assertEqual(evidence["shortcuts_checked"],5)
        self.assertEqual(evidence["fake_registry_keys_checked"],2)
        self.assertFalse(evidence["production_modified"])

    def test_journal_tamper_after_kill_refused(self):
        from unittest.mock import patch
        from installer.rag_p9b_unified_e2e_lab import prepare
        with patch("installer.rag_p9b_unified_e2e_lab.verify_installer_rollback_snapshot",
                   return_value={"verified":True}):
            prepare(self.lab,self.snapshot,self.installed)
        self.assertEqual(self.call("interrupt").returncode,83)
        (self.lab/"interrupted.journal.jsonl").write_text("untrusted",encoding="utf-8")
        refused=self.call("recover")
        self.assertEqual(refused.returncode,2)
        self.assertEqual(json.loads(refused.stdout)["reason"],"JOURNAL_INVALID")

    def test_corrupt_journal_refused(self):
        # Directly verify rejection using prepared lab baseline without
        # tampering with any CodeBridge installation.
        from installer.rag_p9b_unified_e2e_lab import recover
        self.lab.mkdir()
        (self.lab/"identity.json").write_text('{"schema":1,"purpose":"P9B_DISPOSABLE_UNIFIED_LAB","shell_sha":"invalid","file_sha":"invalid"}')
        result=recover(self.lab,self.snapshot)
        self.assertEqual(result["reason"],"BACKUP_CHANGED")

if __name__=="__main__":
    unittest.main()
