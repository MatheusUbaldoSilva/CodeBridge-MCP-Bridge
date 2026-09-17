import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(r"C:\Users\Matheus\CodeBridge-MCP-Bridge")
sys.path.insert(0, str(ROOT / "app_rewrite"))

from external_execute_store import ExternalExecuteStore, ExternalExecuteConflict


class ExternalExecuteStoreTests(unittest.TestCase):
    def test_prepared_request_executes_at_most_once(self):
        with tempfile.TemporaryDirectory() as td:
            store = ExternalExecuteStore(Path(td) / "exec.db")
            row, created = store.reserve(
                "exec_1", "prep_1", "CMD", "hash_a", "runtime_a"
            )
            self.assertTrue(created)
            self.assertEqual(row["state"], "RESERVED")
            row = store.mark_executing("exec_1", "runtime_a")
            self.assertEqual(row["state"], "EXECUTING")
            row = store.mark_finished("exec_1", "OK", 0)
            self.assertEqual(row["state"], "FINISHED")
            again, created = store.reserve(
                "exec_2", "prep_1", "CMD", "hash_a", "runtime_a"
            )
            self.assertFalse(created)
            self.assertEqual(again["execution_request_id"], "exec_1")
            self.assertEqual(again["output"], "OK")

    def test_conflict_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store = ExternalExecuteStore(Path(td) / "exec.db")
            store.reserve("exec_1", "prep_1", "SSH", "hash_a", "runtime_a")
            with self.assertRaises(ExternalExecuteConflict):
                store.reserve(
                    "exec_2", "prep_1", "SSH", "hash_b", "runtime_a"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
