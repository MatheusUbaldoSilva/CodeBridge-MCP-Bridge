import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.sources.execution_inventory import (
    FORBIDDEN_EXECUTION_CONTENT_FIELDS,
    INDEXABLE_EXECUTION_FIELDS,
    SUMMARY_METADATA_FIELDS,
    build_execution_index_record,
)


class RagExecutionInventoryTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "execution_id": "exec_001",
            "request_id": "req_001",
            "target": "POWERSHELL5.1",
            "command_hash": "abc123",
            "failed_command": "Write-Output SECRET_VALUE",
            "state": "FAILED",
            "runtime_instance": "runtime_a",
            "started_at": "2026-10-06T20:00:00Z",
            "finished_at": "2026-10-06T20:00:02Z",
            "exit_code": 1,
            "error_type": "PowerShellCommandError",
            "error_message": "command failed",
            "output": "SECRET RAW OUTPUT",
            "updated_at": "2026-10-06T20:00:02Z",
        }

    def test_handoff_fields_are_represented(self):
        record = build_execution_index_record(self.row)
        self.assertEqual(record["execution_id"], "exec_001")
        self.assertEqual(record["target"], "POWERSHELL5.1")
        self.assertEqual(record["command_hash"], "abc123")
        self.assertEqual(record["status"], "FAILED")
        self.assertEqual(
            record["structured_error"]["error_type"],
            "PowerShellCommandError",
        )
        self.assertIn("summary", record)
        self.assertEqual(
            record["raw_reference"]["execution_id"],
            "exec_001",
        )

    def test_raw_output_and_failed_command_are_never_copied(self):
        record = build_execution_index_record(self.row)
        rendered = repr(record)
        self.assertNotIn("SECRET RAW OUTPUT", rendered)
        self.assertNotIn("SECRET_VALUE", rendered)
        for field in FORBIDDEN_EXECUTION_CONTENT_FIELDS:
            self.assertNotIn(field, record)

    def test_raw_is_reference_only(self):
        record = build_execution_index_record(self.row)
        self.assertEqual(
            record["raw_reference"],
            {
                "execution_id": "exec_001",
                "raw_available": True,
            },
        )

    def test_structured_summary_accepts_metadata_not_content(self):
        record = build_execution_index_record(
            self.row,
            summary={
                "duration_ms": 2000,
                "output_mode": "COMPACT",
                "compaction_applied": True,
                "stdout_lines": 120,
                "stderr_lines": 0,
                "stdout_chars": 22000,
                "stderr_chars": 0,
                "returned_stdout_chars": 7000,
                "unapproved_field": "discard me",
            },
        )
        summary = record["summary"]
        self.assertEqual(summary["duration_ms"], 2000)
        self.assertEqual(summary["output_mode"], "COMPACT")
        self.assertNotIn("unapproved_field", summary)

    def test_summary_rejects_raw_derived_text_fields(self):
        for field in (
            "output",
            "stdout",
            "stderr",
            "text",
            "important_sections",
            "failed_command",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    build_execution_index_record(
                        self.row,
                        summary={field: "raw text"},
                    )

    def test_success_has_no_structured_error(self):
        row = dict(self.row)
        row.update({
            "state": "FINISHED",
            "exit_code": 0,
            "error_type": None,
            "error_message": None,
        })
        record = build_execution_index_record(row)
        self.assertIsNone(record["structured_error"])

    def test_required_identity_fields_are_enforced(self):
        for field in ("execution_id", "target", "command_hash", "state"):
            with self.subTest(field=field):
                row = dict(self.row)
                row[field] = ""
                with self.assertRaises(ValueError):
                    build_execution_index_record(row)

    def test_inventory_constants_do_not_approve_raw_fields(self):
        self.assertTrue({
            "execution_id",
            "target",
            "command_hash",
            "state",
            "error_type",
            "error_message",
        }.issubset(INDEXABLE_EXECUTION_FIELDS))
        self.assertTrue({
            "duration_ms",
            "output_mode",
            "compaction_applied",
        }.issubset(SUMMARY_METADATA_FIELDS))
        self.assertTrue(
            FORBIDDEN_EXECUTION_CONTENT_FIELDS.isdisjoint(
                INDEXABLE_EXECUTION_FIELDS
            )
        )


if __name__ == "__main__":
    unittest.main()
