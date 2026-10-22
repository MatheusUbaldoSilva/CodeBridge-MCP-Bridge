import unittest
from io import StringIO
import json
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

    def test_show_bootstrap_is_read_only_and_diagnostic_only(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_scheduler_preflight",
            return_value={"state": "AUTONOMOUS_SCHEDULING_BLOCKED",
                          "blockers": ["QUEUE_STORE_ABSENT"]},
        ), patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_queue_bootstrap",
            return_value={"state": "BOOTSTRAP_BLOCKED",
                          "blockers": ["QUEUE_DIRECTORY_BOOTSTRAP_PENDING"],
                          "permission_to_bootstrap": False,
                          "directory_created": False},
        ) as bootstrap, patch("sys.stdout", new_callable=StringIO) as out:
            code = main(["--show-bootstrap"])
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report["bootstrap"]["blockers"], ["QUEUE_DIRECTORY_BOOTSTRAP_PENDING"])
        self.assertFalse(report["bootstrap"]["permission_to_bootstrap"])
        bootstrap.assert_called_once_with()

    def test_require_ready_reports_observed_only_not_authorization(self):
        with patch(
            "rag.runtime.incremental_installed_scheduler_preflight_cli.inspect_installed_scheduler_preflight",
            return_value={"state": "PREREQUISITES_OBSERVED_ONLY", "activation_authorized": False},
        ), patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(main(["--require-ready"]), 0)


if __name__ == "__main__":
    unittest.main()
