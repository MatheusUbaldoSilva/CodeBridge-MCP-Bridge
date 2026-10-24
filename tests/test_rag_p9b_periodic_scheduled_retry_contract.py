import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "installer" / "p9b_scheduler_restart_diagnostic_lab.ps1"


@unittest.skipUnless(os.name == "nt", "Windows PowerShell only")
class PeriodicRetryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SCRIPT.read_text(encoding="utf-8")

    def test_powershell_syntax_parses(self):
        check = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::"
            "ParseFile('" + str(SCRIPT).replace("'","''") + "',"
            "[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 2}"
        ], capture_output=True, text=True, timeout=20)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_periodic_trigger_not_manual_restart(self):
        self.assertIn("-RepetitionInterval (New-TimeSpan -Minutes 1)",self.src)
        self.assertIn("-RepetitionDuration (New-TimeSpan -Minutes 4)",self.src)
        self.assertNotIn("Start-ScheduledTask",self.src)

    def test_fail_closed_without_second_attempt(self):
        self.assertIn("AUTOMATIC_PERIODIC_RETRY_UNVERIFIED", self.src)
        self.assertIn("$summary.second_exists -ne $true",self.src)
        self.assertIn("$summary.last_result -ne '0'",self.src)

    def test_temporary_task_and_cleanup(self):
        self.assertIn("REFUSE_PREEXISTING_TASK",self.src)
        self.assertIn("CodeBridge_P9B_Restart_Diagnostic_Lab",self.src)
        self.assertIn("Unregister-ScheduledTask",self.src)
        self.assertIn("TASK_STILL_RUNNING_CLEANUP_REFUSED",self.src)
        self.assertIn("$env:TEMP",self.src)

    def test_real_hard_exit_first_attempt(self):
        self.assertIn("os._exit(87)",self.src)
        self.assertIn("os.fsync(f.fileno())",self.src)


if __name__ == "__main__":
    unittest.main()