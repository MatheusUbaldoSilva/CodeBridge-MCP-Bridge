import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_process_sampling_gate import evaluate_scoped_exit_window

BASE = datetime(2026, 10, 17, 14, tzinfo=timezone.utc)
ROOT = {"pid": 100, "parent_pid": 0, "created_at": "/Date(1600000000000)/",
        "executable_fingerprint": "a" * 64}
CHILD = {"pid": 101, "parent_pid": 100, "created_at": "/Date(1600000001000)/",
         "executable_fingerprint": "b" * 64}

def shot(i, *rows):
    start = BASE + timedelta(seconds=i)
    return {"identity_inventory_ok": True, "unverified_count": 0,
            "source": "WINDOWS_CIM_LAB_SCOPED", "scope_pids": [100, 101],
            "observed_start_utc": start.isoformat(),
            "observed_end_utc": (start + timedelta(milliseconds=50)).isoformat(),
            "verified_pids": [dict(row) for row in rows]}

def good():
    return [shot(0, ROOT, CHILD), shot(1, CHILD), shot(2), shot(3)]

class ScopedSamplingWindowTests(unittest.TestCase):
    def verify(self, data=None, *, now=None, **kwargs):
        return evaluate_scoped_exit_window(
            good() if data is None else data,
            now=BASE + timedelta(seconds=3, milliseconds=100) if now is None else now,
            **kwargs)
    def test_positive_lab_window_never_authorizes(self):
        result = self.verify()
        self.assertEqual(result["state"], "LAB_SCOPED_EXIT_WINDOW_UNPROVEN")
        self.assertEqual(result["samples_verified"], 4)
        self.assertEqual(result["observed_live_pids"], [100, 101])
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])
    def test_no_prior_live_child_blocks(self):
        data = [shot(0, ROOT), shot(1, ROOT), shot(2), shot(3)]
        self.assertIn("EXPECTED_PID_NEVER_OBSERVED", self.verify(data)["issues"])
    def test_only_one_final_absence_blocks(self):
        data = [shot(0, ROOT, CHILD), shot(1, CHILD), shot(2, CHILD), shot(3)]
        self.assertIn("TWO_CONSECUTIVE_ABSENCES_REQUIRED", self.verify(data)["issues"])
    def test_process_reappearing_blocks(self):
        data = [shot(0, ROOT, CHILD), shot(1, CHILD), shot(2, ROOT), shot(3)]
        self.assertIn("PID_REAPPEARED", self.verify(data)["issues"])
    def test_identity_reused_blocks(self):
        data = good()
        data[1]["verified_pids"][0]["created_at"] = "/Date(1600000005000)/"
        self.assertIn("PID_IDENTITY_CHANGED", self.verify(data)["issues"])
    def test_stale_last_sample_blocks(self):
        now = BASE + timedelta(seconds=20)
        self.assertIn("STALE_FINAL_OBSERVATION", self.verify(now=now)["issues"])
    def test_future_dated_sample_blocks(self):
        self.assertIn("OBSERVATION_FROM_FUTURE", self.verify(now=BASE)["issues"])
    def test_gap_blocks(self):
        data = [shot(0, ROOT, CHILD), shot(1, CHILD), shot(20), shot(21)]
        self.assertIn("OBSERVATION_GAP_EXCEEDED",
                      self.verify(data, now=BASE+timedelta(seconds=22))["issues"])
    def test_long_single_observation_blocks(self):
        data = good()
        data[-1]["observed_end_utc"] = (BASE+timedelta(seconds=7)).isoformat()
        self.assertIn("OBSERVATION_TIMEOUT",
                      self.verify(data, now=BASE+timedelta(seconds=8))["issues"])
    def test_incomplete_inventory_blocks(self):
        data = good()
        data[2]["unverified_count"] = 1
        self.assertIn("INVALID_OBSERVATIONS", self.verify(data)["issues"])
    def test_scope_mutation_blocks(self):
        data = good()
        data[1]["scope_pids"] = [100]
        self.assertIn("INVALID_OBSERVATIONS", self.verify(data)["issues"])
    def test_required_trusted_clock(self):
        result = evaluate_scoped_exit_window(good())
        self.assertIn("ValueError", result["issues"])
    def test_bad_limit_type_blocks(self):
        self.assertIn("ValueError", self.verify(max_gap_ms=True)["issues"])

if __name__ == "__main__":
    unittest.main()
