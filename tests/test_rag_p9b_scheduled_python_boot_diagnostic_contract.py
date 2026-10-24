"""Static fail-closed contract for scratch-only Task Scheduler Python boot."""
import os
import subprocess
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"installer"/"p9b_scheduled_python_boot_diagnostic_lab.ps1"


@unittest.skipUnless(os.name=="nt","Windows PowerShell task")
class ScheduledPythonBootContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=SCRIPT.read_text(encoding="utf-8")

    def test_powershell_parses(self):
        result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
            "-Command","$t=$null;$e=$null;[Management.Automation.Language.Parser]::"
            "ParseFile('"+str(SCRIPT).replace("'","''")+"',[ref]$t,[ref]$e)|Out-Null;"
            "if($e.Count){exit 2}"],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_explicit_repo_injected_before_import(self):
        self.assertIn("sys.path.insert(0,r'$repo')",self.text)
        self.assertIn("rag_p9b_scheduled_combined_retry_adapter",self.text)

    def test_honest_failure_without_import(self):
        self.assertIn("SCHEDULED_PYTHON_IMPORT_UNVERIFIED",self.text)
        self.assertIn("BOOT_DIAGNOSTIC_UNPROVEN",self.text)
        self.assertIn("boot.json",self.text)

    def test_scratch_task_cleanup(self):
        self.assertIn("CodeBridge_P9B_Python_Boot_Diagnostic",self.text)
        self.assertIn("$env:TEMP",self.text)
        self.assertIn("REFUSE_PREEXISTING_TASK" if False else "TASK_ALREADY_EXISTS",self.text)
        self.assertIn("Unregister-ScheduledTask",self.text)
        self.assertNotIn("Start-ScheduledTask",self.text)


if __name__=="__main__":
    unittest.main()