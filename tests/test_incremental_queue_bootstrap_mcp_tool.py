"""MCP one-shot bootstrap tool contract; all execution replaced by stubs."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "author_mcp"))
import mcp_server


class RagBootstrapMcpToolTests(unittest.TestCase):
    def test_default_does_not_execute_or_authorize(self):
        fake = {"state": "BOOTSTRAP_PLAN_ONLY", "executed": False,
                "safe_to_publish": False, "scheduler_started": False}
        with patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.bootstrap_installed_queue",
            return_value=fake,
        ) as bootstrap:
            response = mcp_server.codebridge_rag_queue_bootstrap()
        self.assertTrue(response.operation_ok)
        self.assertEqual(response.state, "BOOTSTRAP_PLAN_ONLY")
        self.assertFalse(response.executed)
        self.assertFalse(response.safe_to_publish)
        bootstrap.assert_called_once_with(
            execute=False, operator_approved=False,
            confirmation=None, expected_generation=None,
        )

    def test_explicit_scope_only_delegated_to_dedicated_action(self):
        fake = {"state": "BOOTSTRAP_AUTHORIZATION_MISMATCH", "executed": False,
                "safe_to_publish": False}
        with patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.bootstrap_installed_queue",
            return_value=fake,
        ) as action:
            response = mcp_server.codebridge_rag_queue_bootstrap(
                execute=True, operator_approved=True,
                confirmation="invalid", expected_generation="v1_delta_1ae1d01ea84f4e",
            )
        self.assertEqual(response.state, "BOOTSTRAP_AUTHORIZATION_MISMATCH")
        self.assertFalse(response.executed)
        self.assertFalse(response.safe_to_publish)
        action.assert_called_once()

    def test_unexpected_error_returns_structured_non_publication_result(self):
        with patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.bootstrap_installed_queue",
            side_effect=RuntimeError("synthetic error"),
        ):
            response = mcp_server.codebridge_rag_queue_bootstrap()
        self.assertFalse(response.operation_ok)
        self.assertEqual(response.state, "QUEUE_BOOTSTRAP_ERROR")
        self.assertFalse(response.executed)
        self.assertFalse(response.safe_to_publish)


if __name__ == "__main__":
    unittest.main()
