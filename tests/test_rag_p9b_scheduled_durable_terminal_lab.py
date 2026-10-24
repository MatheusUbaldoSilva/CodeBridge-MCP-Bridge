"""Static safety invariants for the disposable periodic terminal lab."""
import os
import subprocess
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"installer"/"p9b_scheduler_durable_terminal_lab.ps1"

@unittest.skipUnless(os.name=="nt","Windows Scheduled Task")
class ScheduledDurableTerminalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script=SCRIPT.read_text(encoding="utf-8")

    def test_powershell_parser(self):
        result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
            "-Command","$t=$null;$e=$null;[Management.Automation.Language.Parser]::"
            "ParseFile('"+str(SCRIPT).replace("'","''")+"',[ref]$t,[ref]$e)|Out-Null;"
            "if($e.Count){exit 2}"],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_no_manual_restart_and_exact_lab_scope(self):
        self.assertIn("CodeBridge_P9B_Durable_Terminal_Lab",self.script)
        self.assertIn("$env:TEMP",self.script)
        self.assertNotIn("Start-ScheduledTask",self.script)
        self.assertIn("-RepetitionInterval (New-TimeSpan -Minutes 1)",self.script)

    def test_durable_state_before_success(self):
        self.assertIn("mark_disposable_retry_terminal",self.script)
        self.assertIn("reserve_disposable_retry",self.script)
        self.assertIn("P9B_TERMINAL_PERSISTED",self.script)
        self.assertIn("P9B_RECOVERY_ALREADY_TERMINAL",self.script)
        self.assertIn("DURABLE_TERMINAL_PROOF_INVALID",self.script)

    def test_unique_invocations_and_two_attempts(self):
        self.assertIn("$ledger.attempts -ne 2",self.script)
        self.assertIn("$ledger.state -ne 'TERMINAL'",self.script)
        self.assertIn("$first.first_pid -eq $second.second_pid",self.script)
        self.assertIn("$third.third_pid -eq $second.second_pid",self.script)

    def test_cleanup_and_preexisting_refusal(self):
        self.assertIn("REFUSE_PREEXISTING_TASK",self.script)
        self.assertIn("Unregister-ScheduledTask",self.script)
        self.assertIn("TASK_STILL_RUNNING_CLEANUP_REFUSED",self.script)


if __name__=="__main__":
    unittest.main()