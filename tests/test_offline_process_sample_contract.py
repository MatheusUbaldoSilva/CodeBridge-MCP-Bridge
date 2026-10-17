import sys, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_sample_contract import validate_observation_series

T = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)

def sample(number, *, scope=None, rows=None):
    start = T + timedelta(seconds=number)
    return {
        "identity_inventory_ok": True, "unverified_count": 0,
        "verified_pids": [] if rows is None else rows,
        "source": "WINDOWS_CIM_LAB_SCOPED",
        "scope_pids": [100, 101] if scope is None else scope,
        "observed_start_utc": start.isoformat(),
        "observed_end_utc": (start + timedelta(milliseconds=40)).isoformat(),
    }

class ProcessSampleContractTests(unittest.TestCase):
    def test_ordered_scoped_samples_never_authorize(self):
        report = validate_observation_series([sample(0), sample(1), sample(2)])
        self.assertEqual(report["state"], "TIMED_LAB_OBSERVATIONS_VALID_UNPROVEN")
        self.assertEqual(report["samples_valid"], 3)
        self.assertFalse(report["copy_authorized"])
        self.assertFalse(report["all_handles_closed"])
    def test_reordered_samples_block(self):
        report = validate_observation_series([sample(0), sample(2), sample(1)])
        self.assertEqual(report["state"], "BLOCKED")
    def test_changed_scope_blocks(self):
        report = validate_observation_series([sample(0), sample(1, scope=[100]), sample(2)])
        self.assertEqual(report["state"], "BLOCKED")
    def test_unknown_source_blocks(self):
        values = [sample(i) for i in range(3)]
        values[1]["source"] = "MANUAL"
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_unscoped_pid_blocks(self):
        values = [sample(i) for i in range(3)]
        values[1]["verified_pids"] = [{"pid": 202}]
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_incomplete_identity_blocks(self):
        values = [sample(i) for i in range(3)]
        values[1]["verified_pids"] = [{"pid": 100}]
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_duplicate_returned_pid_blocks(self):
        values = [sample(i) for i in range(3)]
        record = {"pid": 100, "parent_pid": 0, "created_at": "20261017",
                  "executable_fingerprint": "a" * 64}
        values[1]["verified_pids"] = [record, dict(record)]
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_missing_clock_blocks(self):
        values = [sample(i) for i in range(3)]
        values[1].pop("observed_end_utc")
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_naive_clock_blocks(self):
        values = [sample(i) for i in range(3)]
        values[0]["observed_start_utc"] = "2026-10-17T12:00:00"
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_inventory_failure_blocks(self):
        values = [sample(i) for i in range(3)]
        values[2]["unverified_count"] = 1
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")
    def test_duplicate_scope_blocks(self):
        values = [sample(i) for i in range(3)]
        values[0]["scope_pids"] = [100,100]
        self.assertEqual(validate_observation_series(values)["state"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
