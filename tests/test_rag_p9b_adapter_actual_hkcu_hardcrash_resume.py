"""Two independent worker processes: real scoped HKCU recovery after hard exit."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

from test_rag_p9b_full_scope_actual_hkcu_integration import FullScopeActualHKCUTests
from installer.rag_p9b_shell_postverify import verify_restored_shell


@unittest.skipUnless(sys.platform=="win32","Windows scoped registry only")
class ActualScopedRecoveryHardCrashTests(unittest.TestCase):
    def setUp(self):
        self.fixture=FullScopeActualHKCUTests("test_isolated_real_hkcu_and_files_combined")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)

    def test_crash_after_files_then_new_worker_restores_and_terminals(self):
        f=self.fixture
        stage=f.lab.parent
        snapshot=stage/"actual-bounded-snapshot.zip"
        shutil.copyfile(f.files_zip,snapshot)
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(),f.file_sha)
        with ZipFile(snapshot) as archive:
            installed=json.loads(archive.read("manifest.json"))["installed_root"]
        cfg=stage/"actual-bounded-config.json"
        journal=stage/"actual-bounded-journal.jsonl"
        retry=stage/"actual-bounded-ledger.json"
        cfg.write_text(json.dumps({
            "lab":str(f.lab), "appdata":str(f.appdata),
            "desktop":str(f.desktop), "installed":installed,
            "token":f.token, "snapshot":str(snapshot),
            "snapshot_sha256":f.file_sha,
            "shell_snapshot":str(f.shell_zip),
            "shell_snapshot_sha256":f.shell_sha,
            "preimage":str(f.preimage),"preimage_sha256":f.pre_sha,
            "journal":str(journal)}),encoding="utf-8")
        sha=hashlib.sha256(cfg.read_bytes()).hexdigest()
        # Each subprocess has independent Python state; retries share only durable journal.
        script = ("import json,sys; "
                  "from installer.rag_p9b_scheduled_combined_retry_adapter "
                  "import run_lab_retry; "
                  "print(json.dumps(run_lab_retry(config=sys.argv[1],"
                  "retry_ledger=sys.argv[2],transaction_sha256=sys.argv[3],"
                  "temp_root=sys.argv[4])),flush=True)")
        env=os.environ.copy()
        env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1])+os.pathsep+env.get("PYTHONPATH","")
        env["P9B_LAB_FAULT_AFTER_FILES"]="1"
        base=[sys.executable,"-c",script,str(cfg),str(retry),sha,str(stage)]
        first=subprocess.run(base,capture_output=True,text=True,timeout=60,env=env)
        self.assertEqual(first.returncode,87,first.stderr[-400:]+first.stdout[-400:])
        self.assertEqual(json.loads(retry.read_text())["attempts"],1)
        env.pop("P9B_LAB_FAULT_AFTER_FILES",None)
        second=subprocess.run(base,capture_output=True,text=True,timeout=60,env=env)
        self.assertEqual(second.returncode,0,second.stderr[-500:])
        proof=json.loads(second.stdout.strip())
        self.assertTrue(proof["verified"],proof)
        self.assertEqual(proof["attempt"],2)
        self.assertEqual(json.loads(retry.read_text())["state"],"TERMINAL")
        third=subprocess.run(base,capture_output=True,text=True,timeout=30,env=env)
        self.assertEqual(third.returncode,0)
        denied=json.loads(third.stdout.strip())
        self.assertEqual(denied["reason"],"DURABLE_TERMINAL_STATE")
        self.assertEqual(json.loads(retry.read_text())["attempts"],2)
        self.assertTrue(verify_restored_shell(
            f.shell_zip,appdata=f.appdata,desktop=f.desktop,
            registry_values=lambda key,names:f.reg.read_key(key))["verified"])


if __name__=="__main__":
    unittest.main()