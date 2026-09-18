import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from constants import JOBS_DB, VALID_TARGETS


TERMINAL_STATES = {"SUCCESS", "FAILED", "CANCELLED", "INTERRUPTED"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else JOBS_DB
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.prune_terminal_jobs()

    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _initialize(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    command TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    visible_at TEXT,
                    prepared_at TEXT,
                    prepared_visible_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    output TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER,
                    error_type TEXT,
                    error_message TEXT
                )
            """)
            columns = {
                row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()
            }
            for name in ("visible_at", "prepared_at", "prepared_visible_at"):
                if name not in columns:
                    con.execute(f"ALTER TABLE jobs ADD COLUMN {name} TEXT")
            con.execute(
                "UPDATE jobs SET state='INTERRUPTED', finished_at=? "
                "WHERE state IN ('RUNNING','PREPARING','PREPARED')",
                (utc_now(),),
            )

    @staticmethod
    def _row(row):
        return None if row is None else dict(row)

    def create(self, target, command):
        if target not in VALID_TARGETS:
            raise ValueError("target invalido")
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("command invalido")
        job_id = uuid.uuid4().hex
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "INSERT INTO jobs(id,target,command,state,created_at) VALUES(?,?,?,?,?)",
                (job_id, target, command, "PENDING", now),
            )
        return self.get(job_id)
    def get(self, job_id):
        with self._lock, self._connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._row(row)

    def mark_visible(self, job_id):
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE jobs SET visible_at=COALESCE(visible_at, ?) WHERE id=?",
                (utc_now(), job_id),
            )
        return self.get(job_id)

    def approve(self, job_id):
        now = utc_now()
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE jobs SET state='APPROVED', approved_at=? "
                "WHERE id=? AND state='PENDING'",
                (now, job_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("job nao esta PENDING")
        return self.get(job_id)

    def cancel_pending(self, job_id):
        now = utc_now()
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE jobs SET state='CANCELLED', finished_at=? "
                "WHERE id=? AND state IN ('PENDING','APPROVED','PREPARING','PREPARED')",
                (now, job_id),
            )
        return bool(cur.rowcount)

    def claim_next(self):
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id FROM jobs WHERE state='APPROVED' "
                "ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                con.commit()
                return None
            cur = con.execute(
                "UPDATE jobs SET state='PREPARING' "
                "WHERE id=? AND state='APPROVED'",
                (row["id"],),
            )
            con.commit()
            if cur.rowcount != 1:
                return None
        return self.get(row["id"])

    def mark_prepared(self, job_id):
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE jobs SET state='PREPARED', prepared_at=? "
                "WHERE id=? AND state='PREPARING'",
                (utc_now(), job_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("job nao esta PREPARING")
        return self.get(job_id)

    def mark_prepared_visible(self, job_id):
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE jobs SET prepared_visible_at=COALESCE(prepared_visible_at, ?) "
                "WHERE id=? AND state='PREPARED'",
                (utc_now(), job_id),
            )
        return self.get(job_id)

    def mark_running(self, job_id):
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE jobs SET state='RUNNING', started_at=? "
                "WHERE id=? AND state='PREPARED'",
                (utc_now(), job_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("job nao esta PREPARED")
        return self.get(job_id)

    def wait_for_field(self, job_id, field, timeout=1.0, poll_interval=0.02):
        if field not in {"visible_at", "prepared_visible_at"}:
            raise ValueError("campo de visibilidade invalido")
        deadline = time.monotonic() + float(timeout)
        while True:
            job = self.get(job_id)
            if job.get(field):
                return True
            if job["state"] in TERMINAL_STATES:
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval)

    def finish(self, job_id, state, output="", exit_code=None,
               error_type=None, error_message=None):
        if state not in TERMINAL_STATES:
            raise ValueError("estado terminal invalido")
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE jobs SET state=?, finished_at=?, output=?, exit_code=?, "
                "error_type=?, error_message=? WHERE id=?",
                (state, utc_now(), str(output), exit_code,
                 error_type, error_message, job_id),
            )
        result = self.get(job_id)
        self.prune_terminal_jobs()
        return result

    def list_visibility_pending(self, limit=100):
        limit = max(1, min(int(limit), 500))
        terminal = tuple(TERMINAL_STATES)
        placeholders = ",".join("?" for _ in terminal)
        sql = (
            "SELECT * FROM jobs WHERE "
            f"(visible_at IS NULL AND state NOT IN ({placeholders})) "
            "OR (state='PREPARED' AND prepared_visible_at IS NULL) "
            "ORDER BY created_at ASC LIMIT ?"
        )
        with self._lock, self._connect() as con:
            rows = con.execute(sql, (*terminal, limit)).fetchall()
        return [self._row(row) for row in rows]

    def prune_terminal_jobs(self, max_age_hours=24, keep_latest=200):
        max_age_hours = max(1, int(max_age_hours))
        keep_latest = max(10, int(keep_latest))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        terminal = tuple(TERMINAL_STATES)
        placeholders = ",".join("?" for _ in terminal)
        deleted = 0
        with self._lock, self._connect() as con:
            cur = con.execute(
                f"DELETE FROM jobs WHERE state IN ({placeholders}) "
                "AND finished_at IS NOT NULL AND finished_at < ?",
                (*terminal, cutoff),
            )
            deleted += int(cur.rowcount or 0)
            rows = con.execute(
                f"SELECT id FROM jobs WHERE state IN ({placeholders}) "
                "ORDER BY COALESCE(finished_at, created_at) DESC "
                "LIMIT -1 OFFSET ?",
                (*terminal, keep_latest),
            ).fetchall()
            if rows:
                ids = [row["id"] for row in rows]
                con.executemany("DELETE FROM jobs WHERE id=?", ((job_id,) for job_id in ids))
                deleted += len(ids)
            if deleted:
                con.execute("PRAGMA optimize")
        return deleted

    def counts(self):
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT state, COUNT(*) AS total FROM jobs GROUP BY state"
            ).fetchall()
        result = {row["state"]: int(row["total"]) for row in rows}
        result["TOTAL"] = sum(result.values())
        return result

    def list_recent(self, limit=20):
        limit = max(1, min(int(limit), 100))
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(row) for row in rows]
