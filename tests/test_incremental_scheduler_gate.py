import tempfile
import sqlite3
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
            self.assertEqual(result["state"],"AUTONOMOUS_SCHEDULING_BLOCKED")
            self.assertIn("QUEUE_STORE_INVALID",result["blockers"])
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

    def test_versioned_synthetic_queue_still_cannot_activate(self):
        with tempfile.TemporaryDirectory() as td:
            store=Path(td)/"jobs"/"incremental_jobs.sqlite3"
            store.parent.mkdir()
            from contextlib import closing
            with closing(sqlite3.connect(store)) as db:
                db.execute("PRAGMA user_version=2")
                from rag.runtime.incremental_job_queue import _SCHEMA
                db.execute(_SCHEMA)
                db.execute("""CREATE TABLE staging_receipts (
                    job_id TEXT PRIMARY KEY, staging_path TEXT,
                    document_sha256 TEXT, document_count INTEGER,
                    chunk_count INTEGER, vector_count INTEGER,
                    validated_at_epoch REAL)""")
                db.commit()
            result=assess_autonomous_worker_gate(
                store,queue_enabled=True,worker_enabled=True,
                scheduler_enabled=True,approved_source_paths=("src/main.py",),
                installed_runtime_verified=True,recovery_verified=True,
                public_integrity_verified=True)
            self.assertEqual(result["state"],"PREREQUISITES_OBSERVED_ONLY")
            self.assertFalse(result["activation_authorized"])
            with closing(sqlite3.connect(store)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0],0)

    def test_partial_versioned_jobs_table_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            store=Path(td)/"jobs"/"incremental_jobs.sqlite3"
            store.parent.mkdir()
            from contextlib import closing
            with closing(sqlite3.connect(store)) as db:
                db.execute("PRAGMA user_version=2")
                db.execute("CREATE TABLE jobs (state TEXT)")
                db.commit()
            result=assess_autonomous_worker_gate(
                store,queue_enabled=True,worker_enabled=True,
                scheduler_enabled=True,approved_source_paths=("src/main.py",),
                installed_runtime_verified=True,recovery_verified=True,
                public_integrity_verified=True)
            self.assertIn("QUEUE_STORE_INVALID",result["blockers"])
            self.assertFalse(result["activation_authorized"])

    def test_optional_durable_fence_invalid_generation_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            store=root/"supervisor_fence.sqlite3"
            queue=root/"queue.sqlite3"
            from rag.runtime.incremental_supervisor_lock import SupervisorLock
            from rag.runtime.incremental_supervisor_fence import issue_generation
            with SupervisorLock(root/"lab.lock") as lock:
                older=issue_generation(store,lock=lock)
                current=issue_generation(store,lock=lock)
            denied=assess_autonomous_worker_gate(
                queue,durable_store=store,expected_durable_generation=older)
            self.assertIn("DURABLE_FENCE_UNVERIFIED",denied["blockers"])
            observed=assess_autonomous_worker_gate(
                queue,durable_store=store,expected_durable_generation=current)
            self.assertNotIn("DURABLE_FENCE_UNVERIFIED",observed["blockers"])
            self.assertFalse(observed["activation_authorized"])
            self.assertFalse(observed["safe_to_publish"])
            self.assertFalse(queue.exists())

    def test_optional_durable_fence_requires_both_arguments(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            queue=root/"queue.sqlite3"
            missing=assess_autonomous_worker_gate(
                queue,expected_durable_generation=1)
            self.assertIn("DURABLE_FENCE_UNVERIFIED",missing["blockers"])
            missing_token=assess_autonomous_worker_gate(
                queue,durable_store=root/"supervisor_fence.sqlite3")
            self.assertIn("DURABLE_FENCE_UNVERIFIED",missing_token["blockers"])
            self.assertFalse(queue.exists())

    def test_complete_synthetic_gate_cannot_activate_or_consume_jobs(self):
        from contextlib import closing
        from rag.runtime.incremental_job_queue import _SCHEMA
        from rag.runtime.incremental_supervisor_lock import SupervisorLock
        from rag.runtime.incremental_supervisor_fence import issue_generation
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            jobs=root/"jobs"
            jobs.mkdir()
            queue=jobs/"incremental_jobs.sqlite3"
            store=root/"supervisor_fence.sqlite3"
            with closing(sqlite3.connect(queue)) as db:
                db.execute("PRAGMA user_version=2")
                db.execute(_SCHEMA)
                db.execute("""CREATE TABLE staging_receipts (
                    job_id TEXT PRIMARY KEY, staging_path TEXT,
                    document_sha256 TEXT, document_count INTEGER,
                    chunk_count INTEGER, vector_count INTEGER,
                    validated_at_epoch REAL)""")
                db.commit()
            with SupervisorLock(root/"lab.lock") as held:
                generation=issue_generation(store,lock=held)
            original_bytes=queue.read_bytes()
            result=assess_autonomous_worker_gate(
                queue,queue_enabled=True,worker_enabled=True,
                scheduler_enabled=True,approved_source_paths=("src/main.py",),
                installed_runtime_verified=True,recovery_verified=True,
                public_integrity_verified=True,durable_store=store,
                expected_durable_generation=generation)
            self.assertEqual(result["state"],"PREREQUISITES_OBSERVED_ONLY",result)
            self.assertEqual(result["blockers"],[])
            self.assertFalse(result["activation_authorized"])
            self.assertFalse(result["scheduler_started"])
            self.assertFalse(result["worker_started"])
            self.assertFalse(result["safe_to_publish"])
            self.assertEqual(queue.read_bytes(),original_bytes)
            with closing(sqlite3.connect(queue)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0],0)
