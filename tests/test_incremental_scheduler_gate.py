import tempfile
import unittest
from pathlib import Path
from rag.runtime.incremental_scheduler_gate import assess_autonomous_worker_gate


class AutonomousWorkerGateTests(unittest.TestCase):
    def test_default_denies_and_does_not_create_queue(self):
        with tempfile.TemporaryDirectory() as td:
            store=Path(td)/"jobs"/"incremental_jobs.sqlite3"
            result=assess_autonomous_worker_gate(store)
            self.assertEqual(result["state"],"AUTONOMOUS_SCHEDULING_BLOCKED")
            self.assertFalse(store.exists())
            self.assertFalse(result["scheduler_started"])
            self.assertFalse(result["safe_to_publish"])

    def test_apparent_prerequisites_do_not_authorize_activation(self):
        with tempfile.TemporaryDirectory() as td:
            store=Path(td)/"queue.sqlite3"
            store.write_bytes(b"fixture: not read")
            result=assess_autonomous_worker_gate(
                store,queue_enabled=True,worker_enabled=True,
                scheduler_enabled=True,approved_source_paths=("src/main.py",),
                installed_runtime_verified=True,recovery_verified=True,
                public_integrity_verified=True)
            self.assertEqual(result["state"],"PREREQUISITES_OBSERVED_ONLY")
            self.assertFalse(result["activation_authorized"])
            self.assertFalse(result["worker_started"])
            self.assertFalse(result["safe_to_publish"])
            self.assertEqual(store.read_bytes(),b"fixture: not read")

    def test_invalid_source_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store=Path(td)/"queue.sqlite3"
            store.write_bytes(b"fixture")
            result=assess_autonomous_worker_gate(
                store,queue_enabled=True,worker_enabled=True,
                scheduler_enabled=True,approved_source_paths=("../other.py",),
                installed_runtime_verified=True,recovery_verified=True,
                public_integrity_verified=True)
            self.assertIn("SOURCE_APPROVAL_REQUIRED",result["blockers"])
