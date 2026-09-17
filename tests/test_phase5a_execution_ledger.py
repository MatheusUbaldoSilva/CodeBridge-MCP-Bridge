import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from execution_ledger import (
    ExecutionLedger,
    ExecutionLedgerConflict,
    ExecutionLedgerStateError,
)


class Phase5AExecutionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "executions.db"
        self.ledger = ExecutionLedger(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_and_read(self):
        row, created = self.ledger.create(
            "exec_001", "req_001", "SSH", "hash_001", "runtime_a"
        )
        self.assertTrue(created)
        self.assertEqual(row["state"], "CREATED")
        self.assertEqual(self.ledger.get("exec_001")["request_id"], "req_001")
        self.assertEqual(self.ledger.get_by_request("req_001")["execution_id"], "exec_001")

    def test_idempotent_create_and_conflict(self):
        first, created = self.ledger.create(
            "exec_002", "req_002", "CMD", "hash_002", "runtime_a"
        )
        second, created_again = self.ledger.create(
            "exec_002", "req_002", "CMD", "hash_002", "runtime_a"
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["created_at"], second["created_at"])
        with self.assertRaises(ExecutionLedgerConflict):
            self.ledger.create(
                "exec_002", "req_002", "CMD", "DIFFERENT", "runtime_a"
            )

    def test_valid_lifecycle(self):
        self.ledger.create(
            "exec_003", "req_003", "POWERSHELL5.1", "hash_003", "runtime_a"
        )
        running = self.ledger.transition(
            "exec_003", "RUNNING", runtime_instance="runtime_a"
        )
        self.assertEqual(running["state"], "RUNNING")
        self.assertIsNotNone(running["started_at"])
        finished = self.ledger.transition(
            "exec_003", "FINISHED", exit_code=0
        )
        self.assertEqual(finished["state"], "FINISHED")
        self.assertEqual(finished["exit_code"], 0)
        self.assertIsNotNone(finished["finished_at"])

    def test_invalid_transition_rejected(self):
        self.ledger.create(
            "exec_004", "req_004", "SSH", "hash_004", "runtime_a"
        )
        with self.assertRaises(ExecutionLedgerStateError):
            self.ledger.transition("exec_004", "FINISHED", exit_code=0)

    def test_persists_across_reopen(self):
        self.ledger.create(
            "exec_005", "req_005", "CMD", "hash_005", "runtime_a"
        )
        self.ledger.transition("exec_005", "RUNNING", runtime_instance="runtime_a")
        reopened = ExecutionLedger(self.db)
        row = reopened.get("exec_005")
        self.assertEqual(row["state"], "RUNNING")
        self.assertEqual(row["runtime_instance"], "runtime_a")

    def test_recover_old_runtime_as_interrupted(self):
        self.ledger.create(
            "exec_006", "req_006", "SSH", "hash_006", "runtime_old"
        )
        self.ledger.transition(
            "exec_006", "RUNNING", runtime_instance="runtime_old"
        )
        changed = self.ledger.interrupt_incomplete_from_other_runtime("runtime_new")
        row = self.ledger.get("exec_006")
        self.assertEqual(changed, 1)
        self.assertEqual(row["state"], "INTERRUPTED")
        self.assertEqual(row["error_type"], "ExecutionInterruptedByRestart")

    def test_terminal_state_cannot_restart(self):
        self.ledger.create(
            "exec_007", "req_007", "CMD", "hash_007", "runtime_a"
        )
        self.ledger.transition("exec_007", "RUNNING", runtime_instance="runtime_a")
        self.ledger.transition(
            "exec_007", "FAILED", error_type="TestError", error_message="boom"
        )
        with self.assertRaises(ExecutionLedgerStateError):
            self.ledger.transition("exec_007", "RUNNING", runtime_instance="runtime_b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
