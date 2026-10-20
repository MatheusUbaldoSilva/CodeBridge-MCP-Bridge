"""Durable V1.03-D-B queue: real Git + SQLite on Windows, never active RAG."""
from __future__ import annotations
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import sys
import json
import tempfile
import unittest

from rag.chunking.provenance import source_sha256
from rag.runtime.incremental_job_queue import (
    claim_approved_job, enqueue_source_event, inspect_job_queue,
    inspect_job, report_staging_failure,
)


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "CodeBridge-MCP-Bridge"
        self.root.mkdir()
        self.file = self.root / "sample.py"
        self.file.write_text("def approved():\n    return 42\n", encoding="utf-8")
        self.db = base / "jobs" / "incremental_jobs.sqlite3"
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "sample.py"], check=True)
        subprocess.run([
            "git", "-C", str(self.root), "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "commit", "-q", "-m", "approved source",
        ], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        self.sha = source_sha256(self.file.read_text(encoding="utf-8"))
        self.event = {
            "approved_paths": ("sample.py",),
            "observed_commit": self.head, "observed_sha256": self.sha,
            "changed_at_epoch": 100.0, "debounce_seconds": 30.0,
        }

    def enqueue(self, **updates):
        kw = {**self.event, **updates}
        return enqueue_source_event(self.db, self.root, "sample.py", **kw)

    def claim(self, **updates):
        kw = {
            "approved_paths": ("sample.py",),
            "queue_enabled": True, "now_epoch": 140.0,
        }
        return claim_approved_job(self.db, self.root, **{**kw, **updates})

    def test_default_disabled_does_not_create_queue_or_execute(self):
        self.assertEqual(self.enqueue(now_epoch=140)["state"], "AUTO_INDEX_DISABLED")
        self.assertEqual(self.claim(queue_enabled=False)["state"], "AUTO_INDEX_DISABLED")
        self.assertEqual(self.claim()["state"], "QUEUE_EMPTY")
        self.assertFalse(self.db.exists())
        self.assertEqual(inspect_job_queue(self.db)["state"], "QUEUE_NOT_INITIALIZED")

    def test_durable_debounce_idempotence_and_claim_lock(self):
        event = self.enqueue(queue_enabled=True, now_epoch=110)
        self.assertEqual(event["state"], "QUEUED_DURABLY")
        self.assertEqual(event["ready_at_epoch"], 130)
        self.assertFalse(event["worker_started"])
        same = self.enqueue(queue_enabled=True, now_epoch=115)
        self.assertEqual(same["job_id"], event["job_id"])
        self.assertEqual(inspect_job_queue(self.db)["total"], 1)
        self.assertEqual(self.claim(now_epoch=129)["state"], "QUEUE_EMPTY")
        claim = self.claim(now_epoch=135)
        self.assertEqual(claim["state"], "CLAIMED_FOR_OFFLINE_STAGING")
        self.assertFalse(claim["worker_started"])
        self.assertEqual(claim["attempts"], 1)
        self.assertEqual(self.claim(now_epoch=136)["state"], "QUEUE_EMPTY")
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["CLAIMED"], 1)
        self.assertEqual(claim["source_path"], "sample.py")
        self.assertFalse(claim["safe_to_publish"])

    def test_queue_survives_new_python_process(self):
        self.enqueue(queue_enabled=True, now_epoch=105)
        child = subprocess.check_output(
            [
                sys.executable, "-c",
                "import json,sys;from pathlib import Path;"
                "from rag.runtime.incremental_job_queue import inspect_job_queue;"
                "print(json.dumps(inspect_job_queue(Path(sys.argv[1]))))",
                str(self.db),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            text=True,
        )
        status = json.loads(child)
        self.assertEqual(status["state"], "QUEUE_INSPECTED")
        self.assertEqual(status["total"], 1)
        self.assertEqual(status["by_state"], {"PENDING": 1})
        self.assertFalse(status["active_index_updated"])

    def test_two_concurrent_claimers_cannot_reserve_same_job(self):
        from concurrent.futures import ThreadPoolExecutor
        self.enqueue(queue_enabled=True, now_epoch=140)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.claim, now_epoch=141) for _ in range(2)]
            answers = [future.result() for future in futures]
        self.assertEqual(
            sorted(answer["state"] for answer in answers),
            ["CLAIMED_FOR_OFFLINE_STAGING", "QUEUE_EMPTY"],
        )
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["CLAIMED"], 1)

    def test_lease_expiration_token_invalidated_and_retry(self):
        self.enqueue(queue_enabled=True, now_epoch=140)
        first = self.claim(now_epoch=140, lease_seconds=15)
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(
            report_staging_failure(
                self.db, first["job_id"], "wrong-token", reason="test",
                queue_enabled=True, now_epoch=141,
            )["state"], "STALE_OR_EXPIRED_LEASE",
        )
        second = self.claim(now_epoch=156, lease_seconds=15)
        self.assertEqual(second["attempts"], 2)
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        self.assertEqual(
            report_staging_failure(
                self.db, first["job_id"], first["lease_token"],
                reason="old-worker-must-not-act", queue_enabled=True,
                now_epoch=157,
            )["state"], "STALE_OR_EXPIRED_LEASE",
        )
        failed = report_staging_failure(
            self.db, second["job_id"], second["lease_token"],
            reason="model-not-ready", now_epoch=157,
            queue_enabled=True, retry_delay_seconds=10,
        )
        self.assertEqual(failed["state"], "SCHEDULED_RETRY")
        self.assertEqual(self.claim(now_epoch=160)["state"], "QUEUE_EMPTY")
        last = self.claim(now_epoch=168)
        self.assertEqual(last["attempts"], 3)
        self.assertEqual(
            report_staging_failure(
                self.db, last["job_id"], last["lease_token"],
                reason="final-failure", now_epoch=169,
                queue_enabled=True,
            )["state"], "FAILED_MAX_ATTEMPTS",
        )
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["FAILED"], 1)
        self.assertEqual(self.claim(now_epoch=220)["state"], "QUEUE_EMPTY")

    def test_dirty_git_and_source_policy_rejected_on_claim(self):
        self.enqueue(queue_enabled=True, now_epoch=105)
        self.file.write_text("def uncommitted():\n    return 0\n", encoding="utf-8")
        result = self.claim(now_epoch=145)
        self.assertEqual(result["state"], "QUEUE_EMPTY")
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["REJECTED"], 1)
        with closing(sqlite3.connect(self.db)) as c:
            last = c.execute("SELECT last_error FROM jobs").fetchone()[0]
        self.assertEqual(last, "SOURCE_NOT_COMMITTED")

    def test_no_approval_no_persistent_db_and_rejected_claim(self):
        self.assertEqual(
            self.enqueue(queue_enabled=True, now_epoch=140,
                         approved_paths=())["state"], "SOURCE_NOT_APPROVED",
        )
        self.assertFalse(self.db.exists())
        self.enqueue(queue_enabled=True, now_epoch=140)
        result = self.claim(approved_paths=(), now_epoch=141)
        self.assertEqual(result["state"], "QUEUE_EMPTY")
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["REJECTED"], 1)

    def test_invalid_db_path_refused_and_unknown_schema_refused(self):
        with self.assertRaises(ValueError):
            enqueue_source_event(
                Path(self.temp.name) / "rag_index.sqlite3",
                self.root, "sample.py", now_epoch=140,
                queue_enabled=True, **self.event,
            )
        self.db.parent.mkdir()
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("CREATE TABLE unrelated(payload TEXT)")
            c.commit()
        with self.assertRaisesRegex(ValueError, "unversioned"):
            self.enqueue(now_epoch=140, queue_enabled=True)
        self.assertFalse((self.root / "rag_index.sqlite3").exists())

    def test_rejected_job_cannot_be_reactivated_by_duplicate_enqueues(self):
        self.enqueue(queue_enabled=True, now_epoch=140)
        self.claim(approved_paths=(), now_epoch=141)
        second = self.enqueue(queue_enabled=True, now_epoch=142)
        self.assertEqual(second["state"], "EXISTING_JOB_TERMINAL")
        self.assertFalse(second["queued"])
        self.assertEqual(inspect_job_queue(self.db)["by_state"]["REJECTED"], 1)

    def test_existing_foreign_versioned_sqlite_is_never_repurposed(self):
        self.db.parent.mkdir()
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("CREATE TABLE foreign_data(secret TEXT)")
            c.execute("INSERT INTO foreign_data VALUES('keep me')")
            c.execute("PRAGMA user_version=1")
            c.commit()
        with self.assertRaisesRegex(ValueError, "schema invalid"):
            self.enqueue(now_epoch=140, queue_enabled=True)
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(
                c.execute("SELECT secret FROM foreign_data").fetchone()[0],
                "keep me",
            )
            self.assertFalse(c.execute(
                "SELECT count(*) FROM sqlite_master WHERE name='jobs'"
            ).fetchone()[0])

    def test_read_only_job_detail_tracks_retry_and_never_exposes_lease_secret(self):
        first = self.enqueue(queue_enabled=True, now_epoch=140)
        job_id = first["job_id"]
        before = self.db.read_bytes()
        waiting = inspect_job(self.db, job_id)
        self.assertEqual(waiting["job_state"], "PENDING")
        self.assertEqual(self.db.read_bytes(), before)
        self.assertNotIn("lease_token", waiting)
        lease = self.claim(now_epoch=141)
        assigned = inspect_job(self.db, job_id)
        self.assertEqual(assigned["job_state"], "CLAIMED")
        self.assertEqual(assigned["attempts"], 1)
        self.assertEqual(
            report_staging_failure(
                self.db, lease["job_id"], lease["lease_token"],
                reason="temporary-offline-error", queue_enabled=True,
                now_epoch=142, retry_delay_seconds=10,
            )["state"], "SCHEDULED_RETRY",
        )
        pending = inspect_job(self.db, job_id)
        self.assertEqual(pending["job_state"], "RETRY")
        self.assertEqual(pending["last_error"], "temporary-offline-error")
        self.assertFalse(pending["safe_to_publish"])
        self.assertEqual(inspect_job(self.db, "bad")["state"], "INVALID_JOB_ID")

    def test_new_git_commit_supersedes_queued_event(self):
        self.enqueue(queue_enabled=True, now_epoch=105)
        self.file.write_text("def new_commit():\n    return 7\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "sample.py"], check=True)
        subprocess.run([
            "git", "-C", str(self.root), "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "commit", "-q", "-m", "new source",
        ], check=True)
        self.assertEqual(self.claim(now_epoch=160)["state"], "QUEUE_EMPTY")
        with closing(sqlite3.connect(self.db)) as c:
            state, reason = c.execute("SELECT state,last_error FROM jobs").fetchone()
        self.assertEqual((state, reason), ("REJECTED", "COMMIT_SUPERSEDED"))


if __name__ == "__main__":
    unittest.main()
