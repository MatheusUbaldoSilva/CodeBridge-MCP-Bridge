import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"installer"/"p9b_scheduled_combined_lab.ps1"


class IndependentCombinedSchedulerLabTests(unittest.TestCase):
    def test_fixed_test_and_fail_closed_cleanup(self):
        script=SCRIPT.read_text(encoding="utf-8-sig")
        for item in ("test_rag_p9b_detached_combined_hardcrash_chain_e2e.py",
                     "test_rag_p9b_real_hkcu_scratch_crash.py",
                     "EXTERNAL_PROCESS_ANCESTRY_VERIFIED",
                     "Get-ScheduledTask","New-ScheduledTaskAction",
                     "Start-ScheduledTask","Unregister-ScheduledTask",
                     "Remove-Item -LiteralPath $folder",
                     "production_modified=$false","nsis_executed=$false",
                     "LAB_FAILED_OR_UNVERIFIED"):
            self.assertIn(item,script)
        for forbidden in ("Stop-Process","Set-ItemProperty",
                          "Start-Process","makensis.exe","CodeBridge-P9B"):
            self.assertNotIn(forbidden,script)

    @unittest.skipUnless(shutil.which("powershell.exe"),"Windows PowerShell only")
    def test_parses(self):
        code=(
            "$t=$null;$e=$null;"
            "[System.Management.Automation.Language.Parser]::ParseFile('"
            +str(SCRIPT).replace("'","''")
            +"',[ref]$t,[ref]$e)|Out-Null; if($e.Count){exit 2}"
        )
        run=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                            "-Command",code],capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)


if __name__=="__main__":unittest.main()
