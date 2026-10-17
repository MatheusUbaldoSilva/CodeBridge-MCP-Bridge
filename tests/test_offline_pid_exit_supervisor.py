"""Proof-of-concept exit supervisor is observation-only and fail closed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.offline_pid_exit_supervisor import supervise_expected_exits

OLD = {"pid": 120, "name": "python.exe", "created_at": "20261015101000",
       "executable_fingerprint": "a" * 64}
NEW = {**OLD, "created_at": "20261015101100"}


def shot(rows, *, valid=True, missing=0):
    return {"identity_inventory_ok": valid, "unverified_count": missing,
            "verified_pids": rows}


def sequence(*shots):
    cursor = iter(shots)
    return lambda: next(cursor)


class ExitSupervisorTests(unittest.TestCase):
    def test_never_seen_active_cannot_claim_exit(self):
        result = supervise_expected_exits([OLD], observer=sequence(shot([]), shot([])),
                                          samples=2, sleeper=lambda x: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("EXPECTED_PROCESS_NEVER_SEEN_ACTIVE", result["issues"])
        self.assertEqual(result["samples_completed"], 2)
        self.assertFalse(result["copy_authorized"])
        self.assertFalse(result["all_handles_closed"])

    def test_active_then_two_absences(self):
        result = supervise_expected_exits([OLD], observer=sequence(
            shot([OLD]), shot([]), shot([])), samples=3, sleeper=lambda x: None)
        self.assertEqual(result["state"], "EXPECTED_PIDS_ABSENT_UNPROVEN")
        self.assertEqual(result["observed_exit_pids"], [120])

    def test_one_absence_is_not_enough(self):
        result = supervise_expected_exits([OLD], observer=sequence(shot([OLD]), shot([])),
                                          samples=2, sleeper=lambda x: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("AWAITING_SECOND_ABSENCE_SAMPLE", result["issues"])

    def test_partial_observation_does_not_prove_all_expected_exited(self):
        another = {**OLD, "pid": 121}
        result = supervise_expected_exits([OLD, another], observer=sequence(
            shot([OLD]), shot([]), shot([])), samples=3, sleeper=lambda x: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("EXPECTED_PROCESS_NEVER_SEEN_ACTIVE", result["issues"])

    def test_process_reappearing_resets_consecutive_absence(self):
        result = supervise_expected_exits([OLD], observer=sequence(
            shot([OLD]), shot([]), shot([OLD]), shot([]), shot([])),
            samples=5, sleeper=lambda x: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("EXPECTED_PID_REAPPEARED", result["issues"])
        self.assertEqual(result["samples_completed"], 3)
        self.assertFalse(result["production_quiescence_proven"])

    def test_pid_reuse_blocks(self):
        result = supervise_expected_exits([OLD], observer=sequence(shot([NEW])),
                                          samples=2, sleeper=lambda x: None)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("PID_REUSED_OR_IDENTITY_CHANGED", result["issues"])

    def test_unverifiable_inventory_blocks(self):
        for snapshot in (shot([], valid=False), shot([], missing=1)):
            with self.subTest(snapshot=snapshot):
                result = supervise_expected_exits([OLD], observer=lambda s=snapshot: s,
                                                 samples=2, sleeper=lambda x: None)
                self.assertEqual(result["state"], "BLOCKED")

    def test_missing_or_duplicate_baseline_blocks(self):
        for baseline in ([], [OLD, OLD], [{**OLD, "created_at": ""}]):
            with self.subTest(baseline=baseline):
                result = supervise_expected_exits(baseline, samples=2,
                                                 observer=lambda: shot([]))
                self.assertEqual(result["state"], "BLOCKED")

    def test_raised_inventory_failure_blocks(self):
        result = supervise_expected_exits([OLD], observer=lambda: (_ for _ in ()).throw(
            RuntimeError("inventory failed")), samples=2)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["production_quiescence_proven"])


if __name__ == "__main__":
    unittest.main()
