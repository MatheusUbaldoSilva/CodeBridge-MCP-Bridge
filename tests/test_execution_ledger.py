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


class ExecutionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "executions.db"
        self.ledger = ExecutionLedger(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def create_running(self, execution_id="exec_output"):
        self.ledger.create(
            execution_id,
            "req_" + execution_id,
            "POWERSHELL5.1",
            "hash_" + execution_id,
            "runtime_a",
        )
        self.ledger.transition(
            execution_id,
            "RUNNING",
            runtime_instance="runtime_a",
        )
        return execution_id

    def test_create_and_read(self):
        row, created = self.ledger.create(
            "exec_001", "req_001", "SSH", "hash_001", "runtime_a"
        )
        self.assertTrue(created)
        self.assertEqual(row["state"], "CREATED")
        self.assertEqual(self.ledger.get("exec_001")["request_id"], "req_001")
        self.assertEqual(
            self.ledger.get_by_request("req_001")["execution_id"],
            "exec_001",
        )

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
                "exec_002",
                "req_002",
                "CMD",
                "DIFFERENT",
                "runtime_a",
            )

    def test_valid_lifecycle(self):
        self.ledger.create(
            "exec_003",
            "req_003",
            "POWERSHELL5.1",
            "hash_003",
            "runtime_a",
        )
        running = self.ledger.transition(
            "exec_003",
            "RUNNING",
            runtime_instance="runtime_a",
        )
        self.assertEqual(running["state"], "RUNNING")
        self.assertIsNotNone(running["started_at"])
        finished = self.ledger.transition(
            "exec_003",
            "FINISHED",
            exit_code=0,
        )
        self.assertEqual(finished["state"], "FINISHED")
        self.assertEqual(finished["exit_code"], 0)
        self.assertIsNotNone(finished["finished_at"])

    def test_invalid_transition_rejected(self):
        self.ledger.create(
            "exec_004", "req_004", "SSH", "hash_004", "runtime_a"
        )
        with self.assertRaises(ExecutionLedgerStateError):
            self.ledger.transition(
                "exec_004",
                "FINISHED",
                exit_code=0,
            )

    def test_persists_across_reopen(self):
        self.ledger.create(
            "exec_005", "req_005", "CMD", "hash_005", "runtime_a"
        )
        self.ledger.transition(
            "exec_005",
            "RUNNING",
            runtime_instance="runtime_a",
        )
        reopened = ExecutionLedger(self.db)
        row = reopened.get("exec_005")
        self.assertEqual(row["state"], "RUNNING")
        self.assertEqual(row["runtime_instance"], "runtime_a")

    def test_recover_old_runtime_as_interrupted(self):
        self.ledger.create(
            "exec_006",
            "req_006",
            "SSH",
            "hash_006",
            "runtime_old",
        )
        self.ledger.transition(
            "exec_006",
            "RUNNING",
            runtime_instance="runtime_old",
        )
        changed = self.ledger.interrupt_incomplete_from_other_runtime(
            "runtime_new"
        )
        row = self.ledger.get("exec_006")
        self.assertEqual(changed, 1)
        self.assertEqual(row["state"], "INTERRUPTED")
        self.assertEqual(
            row["error_type"],
            "ExecutionInterruptedByRestart",
        )

    def test_terminal_state_cannot_restart(self):
        self.ledger.create(
            "exec_007", "req_007", "CMD", "hash_007", "runtime_a"
        )
        self.ledger.transition(
            "exec_007",
            "RUNNING",
            runtime_instance="runtime_a",
        )
        self.ledger.transition(
            "exec_007",
            "FAILED",
            error_type="TestError",
            error_message="boom",
        )
        with self.assertRaises(ExecutionLedgerStateError):
            self.ledger.transition(
                "exec_007",
                "RUNNING",
                runtime_instance="runtime_b",
            )

    def test_chunk_cursor(self):
        execution_id = self.create_running()
        self.ledger.append_output(execution_id, "ABC")
        self.ledger.append_output(execution_id, "DEFG")
        first = self.ledger.read_output(execution_id, 0, 4)
        self.assertEqual(first["text"], "ABCD")
        self.assertEqual(first["next_cursor"], 4)
        self.assertTrue(first["has_more"])
        second = self.ledger.read_output(execution_id, 4, 4)
        self.assertEqual(second["text"], "EFG")
        self.assertEqual(second["next_cursor"], 7)

    def test_terminal_eof(self):
        execution_id = self.create_running()
        self.ledger.append_output(execution_id, "HELLO")
        self.ledger.transition(
            execution_id,
            "FINISHED",
            runtime_instance="runtime_a",
            exit_code=0,
            output="HELLO",
        )
        result = self.ledger.read_output(execution_id, 0, 10)
        self.assertTrue(result["complete"])
        self.assertTrue(result["eof"])
        self.assertFalse(result["has_more"])

    def test_sync_preserves_existing_append_only_stream(self):
        execution_id = self.create_running()
        self.ledger.append_output(execution_id, "BAD")
        result = self.ledger.sync_output(
            execution_id,
            "GOOD-OUTPUT",
            chunk_size=1024,
        )
        self.assertFalse(result["rewritten"])
        self.assertEqual(result["reason"], "append_only")
        output = self.ledger.read_output(execution_id, 0, 100)
        self.assertEqual(output["text"], "BAD")

    def test_sync_initial_fill(self):
        execution_id = self.create_running()
        result = self.ledger.sync_output(
            execution_id,
            "GOOD-OUTPUT",
            chunk_size=1024,
        )
        self.assertFalse(result["rewritten"])
        self.assertEqual(result["reason"], "initial_fill")
        output = self.ledger.read_output(execution_id, 0, 100)
        self.assertEqual(output["text"], "GOOD-OUTPUT")

    def test_persists_chunks_after_reopen(self):
        execution_id = self.create_running()
        self.ledger.append_output(execution_id, "ONE")
        self.ledger.append_output(execution_id, "TWO")
        reopened = ExecutionLedger(self.db)
        result = reopened.read_output(execution_id, 0, 100)
        self.assertEqual(result["text"], "ONETWO")
        self.assertEqual(result["available_chars"], 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
