import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from execution_ledger import ExecutionLedger


class ExecutionErrorContractLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "executions.db"
        self.ledger = ExecutionLedger(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_failed_command_is_preserved_on_failure(self):
        command = "cmd.exe /c exit 7"
        self.ledger.create(
            "exec_fail", "req_fail", "POWERSHELL5.1", "hash_fail",
            "runtime_a", failed_command=command,
        )
        self.ledger.transition(
            "exec_fail", "RUNNING", runtime_instance="runtime_a"
        )
        row = self.ledger.transition(
            "exec_fail", "FAILED", runtime_instance="runtime_a",
            exit_code=7, error_type="PowerShellCommandError",
            error_message="falhou",
        )
        self.assertEqual(row["failed_command"], command)
        reopened = ExecutionLedger(self.db)
        self.assertEqual(
            reopened.get("exec_fail")["failed_command"], command
        )

    def test_success_clears_command_text(self):
        command = "Write-Output SECRET_SUCCESS_TEXT"
        self.ledger.create(
            "exec_ok", "req_ok", "POWERSHELL5.1", "hash_ok",
            "runtime_a", failed_command=command,
        )
        self.ledger.transition(
            "exec_ok", "RUNNING", runtime_instance="runtime_a"
        )
        row = self.ledger.transition(
            "exec_ok", "FINISHED", runtime_instance="runtime_a",
            exit_code=0, output="OK",
        )
        self.assertEqual(row["failed_command"], "")

    def test_cancel_keeps_command_for_diagnostics(self):
        command = "Start-Sleep -Seconds 30"
        self.ledger.create(
            "exec_cancel", "req_cancel", "POWERSHELL5.1",
            "hash_cancel", "runtime_a", failed_command=command,
        )
        row = self.ledger.transition(
            "exec_cancel", "CANCELLED", runtime_instance="runtime_a",
            error_type="ExecutionCancelledBeforeStart",
            error_message="cancelado",
        )
        self.assertEqual(row["failed_command"], command)


if __name__ == "__main__":
    unittest.main()