"""Static and parser contract for the guarded PowerShell scheduler launcher."""
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "installer" / "p9b_scheduled_readonly_launcher.ps1"


class PowerShellScheduledLauncherContractTests(unittest.TestCase):
    def test_launcher_has_explicit_readonly_guards_and_cleanup(self):
        text=SCRIPT.read_text(encoding="utf-8-sig")
        for required in (
            "P9B_REFUSE_PREEXISTING_TASK",
            "New-ScheduledTaskAction",
            "New-ScheduledTaskPrincipal",
            "Register-ScheduledTask",
            "Start-ScheduledTask",
            "Unregister-ScheduledTask",
            "SCHEDULED_SUPERVISOR_READONLY_ATTESTED",
            "SCHEDULED_READONLY_LAUNCH_VERIFIED",
            "Remove-Item -LiteralPath $folder",
            "$proof.shutdown_plan_verified -ne $true",
            "$proof.authorized -ne $false",
            "$proof.installer_executed -ne $false",
            "$proof.shutdown_signals_sent -ne $false",
            "$proof.production_modified -ne $false",
        ):
            self.assertIn(required,text)
        self.assertNotIn("Stop-Process",text)
        self.assertNotIn("Start-Process",text)
        self.assertNotIn("Set-ItemProperty",text)
        self.assertNotIn("makensis.exe",text)

    @unittest.skipUnless(shutil.which("powershell.exe"),"PowerShell Windows only")
    def test_powershell_parser_has_no_errors(self):
        command = (
            "$tokens=$null;$errors=$null;"
            "[System.Management.Automation.Language.Parser]::ParseFile("
            "'" + str(SCRIPT).replace("'","''") + "',"
            "[ref]$tokens,[ref]$errors)|Out-Null;"
            "if($errors.Count -ne 0){$errors|ForEach-Object {Write-Output $_};exit 3}"
        )
        run=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                            "-Command",command],capture_output=True,text=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)


if __name__=="__main__":unittest.main()
