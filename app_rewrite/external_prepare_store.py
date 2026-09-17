import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def command_hash(command):
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


class ExternalPrepareConflict(RuntimeError):
    pass


class ExternalPrepareStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _initialize(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS prepared_commands (
                    request_id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    command_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    runtime_instance TEXT NOT NULL,
                    prepared_at TEXT,
                    finished_at TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _row(row):
        return None if row is None else dict(row)

    def get(self, request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM prepared_commands WHERE request_id=?", (request_id,)
            ).fetchone()
        return self._row(row)

    def reserve(self, request_id, target, command, runtime_instance):
        digest = command_hash(command)
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM prepared_commands WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is not None:
                if row["target"] != target or row["command_hash"] != digest:
                    raise ExternalPrepareConflict(
                        "request_id reutilizado com target/comando diferente"
                    )
                con.commit()
                return self._row(row), False
            con.execute(
                "INSERT INTO prepared_commands(request_id,target,command_hash,state,runtime_instance,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (request_id, target, digest, "RESERVED", runtime_instance, now, now),
            )
            con.commit()
        return self.get(request_id), True

    def mark_preparing(self, request_id, runtime_instance):
        return self._set_state(request_id, "PREPARING", runtime_instance=runtime_instance)

    def mark_prepared(self, request_id, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE prepared_commands SET state='PREPARED',runtime_instance=?,prepared_at=?,updated_at=?,error_message=NULL WHERE request_id=?",
                (runtime_instance, now, now, request_id),
            )
        return self.get(request_id)

    def mark_failed(self, request_id, message):
        return self._set_state(request_id, "FAILED", error_message=str(message), finished=True)

    def mark_discarded(self, request_id):
        return self._set_state(request_id, "DISCARDED", finished=True)

    def _set_state(self, request_id, state, runtime_instance=None,
                   error_message=None, finished=False):
        now = utc_now()
        fields = ["state=?", "updated_at=?"]
        values = [state, now]
        if runtime_instance is not None:
            fields.append("runtime_instance=?")
            values.append(runtime_instance)
        if error_message is not None:
            fields.append("error_message=?")
            values.append(error_message)
        if finished:
            fields.append("finished_at=?")
            values.append(now)
        values.append(request_id)
        with self._lock, self._connect() as con:
            con.execute(
                f"UPDATE prepared_commands SET {','.join(fields)} WHERE request_id=?",
                tuple(values),
            )
        return self.get(request_id)

    def reset_for_new_runtime(self, request_id, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE prepared_commands SET state='RESERVED',runtime_instance=?,prepared_at=NULL,finished_at=NULL,error_message=NULL,updated_at=? WHERE request_id=?",
                (runtime_instance, now, request_id),
            )
        return self.get(request_id)
