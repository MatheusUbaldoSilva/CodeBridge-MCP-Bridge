import unittest
from io import StringIO
from unittest.mock import patch

from rag.runtime.incremental_installed_scheduler_preflight_cli import main


class SchedulerDiagnosticExitTests(unittest.TestCase):
    def test_require_ready_rejects_blocked_prerequisites(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_scheduler_preflight",
            return_value={"state": "AUTONOMOUS_SCHEDULING_BLOCKED", "blockers": ["QUEUE_STORE_ABSENT"]},
        ), patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["--require-ready"]), 2)

    def test_default_diagnostic_succeeds_when_blocked(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_scheduler_preflight",
            return_value={"state": "AUTONOMOUS_SCHEDULING_BLOCKED", "blockers": ["QUEUE_STORE_ABSENT"]},
        ), patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main([]), 0)

    def test_require_ready_reports_observed_only_not_authorization(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_scheduler_preflight",
            return_value={"state": "PREREQUISITES_OBSERVED_ONLY", "activation_authorized": False},
        ), patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["--require-ready"]), 0)


if __name__ == "__main__":
    unittest.main()
