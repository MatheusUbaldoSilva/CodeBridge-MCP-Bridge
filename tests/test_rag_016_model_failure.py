import unittest
from pathlib import Path

from rag.benchmark.model_failure import run_model_failure_canary


class Rag016ModelFailureTests(unittest.TestCase):
    def test_missing_models_fail_closed_without_process(self):
        result = run_model_failure_canary(
            Path(r"C:\llama\llama-server.exe")
        )

        self.assertEqual(len(result.failures), 2)
        for failure in result.failures:
            self.assertEqual(failure.final_state, "UNLOADED")
            self.assertFalse(failure.process_alive)
            self.assertIsNone(failure.pid)
            self.assertTrue(failure.expected_error)


if __name__ == "__main__":
    unittest.main()
