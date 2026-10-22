"""Isolated one-shot queue-bootstrap contract; NEVER touches user AppData."""
import tempfile
import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch

from rag.runtime.incremental_authorized_queue_bootstrap import bootstrap_installed_queue
from rag.runtime.incremental_job_queue import inspect_job_queue
from rag.runtime.incremental_supervisor_fence import observe_generation


class IsolatedInstalledQueueBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "CodeBridge" / "rag"
        self.root.mkdir(parents=True)
        self.legacy = self.root / "rag_index.sqlite3"
        self.legacy.write_bytes(b"synthetic")
        self.generation = "v1_delta_1ae1d01ea84f4e"
        self.pointer = {
            "state": "PUBLIC_POINTER_OBSERVED",
            "generation": self.generation,
        }
        (self.root / "active-generation.json").write_text(
            json.dumps({"schema_version": 1, "generation": self.generation}),
            encoding="utf-8",
        )
        selected = self.root / "generations" / self.generation
        selected.mkdir(parents=True)
        (selected / "rag_index.sqlite3").write_bytes(b"synthetic public")
        (selected / "rag-index-manifest.json").write_text("{}", encoding="utf-8")
        self.jobs = self.root / "jobs"

    def operation(self, **kwargs):
        with patch.dict(os.environ, {"LOCALAPPDATA": self.temp.name}), patch(
            "rag.runtime.incremental_installed_queue_bootstrap_preflight.resolve_rag_sqlite_path",
            return_value=self.legacy,
        ), patch(
            "rag.runtime.incremental_scheduler_public_pointer.resolve_rag_sqlite_path",
            return_value=self.legacy,
        ), patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.resolve_rag_sqlite_path",
            return_value=self.legacy,
        ):
            return bootstrap_installed_queue(**kwargs)

    def test_default_preview_has_no_side_effects(self):
        result = self.operation()
        self.assertEqual(result["state"], "BOOTSTRAP_PLAN_ONLY")
        self.assertFalse(result["executed"])
        self.assertFalse(self.jobs.exists())
        self.assertEqual(result["public_generation"], self.generation)
        self.assertIn(self.generation, result["confirmation"])

    def test_explicit_authorization_required_even_with_execute_true(self):
        plan = self.operation()
        for kwargs in (
            {"execute": True},
            {"execute": True, "operator_approved": True},
            {"execute": True, "operator_approved": True, "confirmation": "wrong",
             "expected_generation": self.generation},
            {"execute": True, "operator_approved": True,
             "confirmation": plan["confirmation"], "expected_generation": "legacy"},
        ):
            with self.subTest(kwargs=kwargs):
                result = self.operation(**kwargs)
                self.assertEqual(result["state"], "BOOTSTRAP_AUTHORIZATION_MISMATCH")
                self.assertFalse(self.jobs.exists())

    def test_approved_bootstrap_creates_only_queue_and_fence(self):
        plan = self.operation()
        original_public = (self.root / "generations" / self.generation /
                           "rag_index.sqlite3").read_bytes()
        result = self.operation(
            execute=True, operator_approved=True,
            confirmation=plan["confirmation"],
            expected_generation=self.generation,
        )
        self.assertEqual(result["state"], "QUEUE_BOOTSTRAPPED_NO_SCHEDULER")
        self.assertTrue(result["executed"])
        self.assertFalse(result["worker_started"])
        self.assertFalse(result["scheduler_started"])
        self.assertFalse(result["active_index_updated"])
        self.assertTrue(observe_generation(
            self.jobs / "supervisor_fence.sqlite3", result["fence_generation"],
        ))
        self.assertEqual(
            inspect_job_queue(self.jobs / "incremental_jobs.sqlite3")["total"], 0,
        )
        self.assertEqual((self.root / "generations" / self.generation /
                          "rag_index.sqlite3").read_bytes(), original_public)
        repeated = self.operation()
        self.assertEqual(repeated["state"], "BOOTSTRAP_BLOCKED")

    def test_rejects_unrecognized_jobs_directory_without_altering_it(self):
        self.jobs.mkdir()
        unknown = self.jobs / "unrelated.txt"
        unknown.write_text("KEEP", encoding="utf-8")
        result = self.operation()
        self.assertEqual(result["state"], "BOOTSTRAP_BLOCKED")
        self.assertEqual(result["reason"], "UNRECOGNIZED_JOBS_CONTENT")
        self.assertEqual(unknown.read_text(), "KEEP")

    def test_unapproved_localappdata_root_never_initializes(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root)}), patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.resolve_rag_sqlite_path",
            return_value=self.legacy,
        ):
            report = bootstrap_installed_queue()
        self.assertEqual(report["reason"], "UNAPPROVED_INSTALLED_ROOT")
        self.assertFalse(self.jobs.exists())

    def test_bootstrap_interrupted_after_queue_creation_reports_partial_state(self):
        plan = self.operation()
        from rag.runtime.incremental_job_queue import _connection
        from contextlib import closing
        from unittest.mock import patch
        def interrupted_fence(*_args, **_kwargs):
            raise OSError("synthetic disk failure")
        with patch(
            "rag.runtime.incremental_authorized_queue_bootstrap.issue_generation",
            side_effect=interrupted_fence,
        ):
            result = self.operation(
                execute=True, operator_approved=True,
                confirmation=plan["confirmation"],
                expected_generation=self.generation,
            )
        self.assertEqual(result["state"], "BOOTSTRAP_REVIEW_REQUIRED")
        self.assertTrue(result["executed"])
        self.assertTrue(result["queue_present"])
        self.assertFalse(result["fence_present"])
        self.assertFalse(result["worker_started"])
        self.assertEqual(self.operation()["state"], "BOOTSTRAP_BLOCKED")

    def test_pending_transition_prevents_bootstrap(self):
        (self.root / "production-generation-transition.json").write_text("{}")
        result = self.operation()
        self.assertEqual(result["state"], "BOOTSTRAP_BLOCKED")
        self.assertFalse(self.jobs.exists())


if __name__ == "__main__":
    unittest.main()
