import unittest

from rag.runtime.incremental_supervisor_lifecycle import (
    SupervisorSnapshot, SupervisorState, transition,
)


class SupervisorLifecycleTests(unittest.TestCase):
    def test_start_and_graceful_stop(self):
        snapshot = SupervisorSnapshot()
        for event, expected in (
            ("request_start", SupervisorState.STARTING),
            ("started", SupervisorState.RUNNING),
            ("request_stop", SupervisorState.STOPPING),
            ("stopped", SupervisorState.STOPPED),
        ):
            snapshot, result = transition(
                snapshot, event,
                **({"expected_generation": snapshot.generation}
                   if event in ("started", "stopped", "failed") else {}),
            )
            self.assertTrue(result["accepted"])
            self.assertEqual(snapshot.state, expected)
            self.assertFalse(result["worker_started"])
            self.assertFalse(result["safe_to_publish"])
        self.assertEqual(snapshot.generation, 1)
        self.assertFalse(snapshot.stop_requested)

    def test_duplicate_start_rejected(self):
        snapshot, _ = transition(SupervisorSnapshot(), "request_start")
        duplicate, result = transition(snapshot, "request_start")
        self.assertEqual(duplicate, snapshot)
        self.assertFalse(result["accepted"])

    def test_failure_must_reset_not_restart(self):
        snapshot, _ = transition(SupervisorSnapshot(), "request_start")
        failed, _ = transition(snapshot, "failed", expected_generation=snapshot.generation)
        self.assertEqual(failed.state, SupervisorState.FAILED)
        denied, result = transition(failed, "request_start")
        self.assertFalse(result["accepted"])
        self.assertEqual(denied, failed)
        reset, _ = transition(failed, "reset")
        self.assertEqual(reset.state, SupervisorState.STOPPED)

    def test_stop_during_start_disallows_started(self):
        starting, _ = transition(SupervisorSnapshot(), "request_start")
        stopping, _ = transition(starting, "request_stop")
        self.assertTrue(stopping.stop_requested)
        unchanged, result = transition(stopping, "started")
        self.assertFalse(result["accepted"])
        self.assertEqual(unchanged, stopping)

    def test_repeated_stop_is_denied_and_state_immutable(self):
        original = SupervisorSnapshot()
        unchanged, result = transition(original, "request_stop")
        self.assertIs(unchanged, original)
        self.assertFalse(result["accepted"])

    def test_stale_started_callback_after_restart_denied(self):
        old, _ = transition(SupervisorSnapshot(), "request_start")
        running, _ = transition(old, "started", expected_generation=old.generation)
        stopping, _ = transition(running, "request_stop")
        stopped, _ = transition(stopping, "stopped", expected_generation=stopping.generation)
        restarting, _ = transition(stopped, "request_start")
        unchanged, result = transition(restarting, "started", expected_generation=old.generation)
        self.assertEqual(unchanged, restarting)
        self.assertEqual(result["reason"], "STALE_OR_MISSING_GENERATION")

    def test_missing_generation_callbacks_denied(self):
        starting, _ = transition(SupervisorSnapshot(), "request_start")
        unchanged, result = transition(starting, "started")
        self.assertIs(unchanged, starting)
        self.assertEqual(result["reason"], "STALE_OR_MISSING_GENERATION")
