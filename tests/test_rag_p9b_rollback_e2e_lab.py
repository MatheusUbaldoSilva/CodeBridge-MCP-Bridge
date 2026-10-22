import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CODE=("import sys;sys.path.insert(0,sys.argv[1]);"
      "from installer.rag_p9b_rollback_e2e_lab import main;"
      "sys.argv=[sys.argv[0]]+sys.argv[2:];raise SystemExit(main())")


class RollbackE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"e2e-lab"

    def invoke(self,operation):
        return subprocess.run([sys.executable,"-c",CODE,str(REPO),operation,str(self.root)],
                              capture_output=True,text=True,timeout=10)

    def test_crash_then_independent_restore(self):
        created=self.invoke("setup")
        self.assertEqual(created.returncode,0,created.stderr)
        crash=self.invoke("crash")
        self.assertEqual(crash.returncode,83,crash.stderr)
        interrupted=self.root/"roaming"/"Microsoft"/"Windows"/"Start Menu"/"Programs"/"CodeBridge"/"CodeBridge.lnk"
        self.assertEqual(interrupted.read_bytes(),b"PARTIALLY_UPDATED_BY_CRASHED_CHILD")
        self.assertEqual(json.loads((self.root/"fake_registry_state.json").read_text())["changed"],True)
        rescue=self.invoke("rescue")
        self.assertEqual(rescue.returncode,0,rescue.stderr)
        result=json.loads(rescue.stdout)
        self.assertEqual(result["state"],"LAB_E2E_RECOVERED")
        self.assertEqual(result["fake_registry_keys_checked"],2)
        self.assertEqual(result["files_checked"],5)
        self.assertFalse(result["production_modified"])
        self.assertEqual(interrupted.read_bytes(),b"baseline-0")
        self.assertEqual(len(json.loads((self.root/"fake_registry_state.json").read_text())),2)

    def test_unexpected_journal_blocks_rescue(self):
        self.assertEqual(self.invoke("setup").returncode,0)
        self.assertEqual(self.invoke("crash").returncode,83)
        (self.root/"crash.journal.jsonl").write_text("corrupt",encoding="utf-8")
        refusal=self.invoke("rescue")
        self.assertEqual(refusal.returncode,2)
        self.assertIn("JOURNAL_INVALID",refusal.stdout)


if __name__=="__main__":
    unittest.main()
