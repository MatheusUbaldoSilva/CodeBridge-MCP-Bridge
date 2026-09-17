import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


MAX_FINAL_OUTPUT_CHARS = 250000
CHUNK_SIZE_CHARS = 16384


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ExternalExecuteConflict(RuntimeError):
    pass


class ExternalExecuteStore:
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
                CREATE TABLE IF NOT EXISTS external_executions (
                    execution_request_id TEXT PRIMARY KEY,
                    prepared_request_id TEXT NOT NULL UNIQUE,
                    target TEXT NOT NULL,
                    command_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    runtime_instance TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    output TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS external_execution_chunks (
                    execution_request_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(execution_request_id, seq)
                )
            """)

    @staticmethod
    def _row(row):
        return None if row is None else dict(row)

    def get_by_execution(self, execution_request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM external_executions WHERE execution_request_id=?",
                (execution_request_id,),
            ).fetchone()
        return self._row(row)
    def get_by_prepared(self, prepared_request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM external_executions WHERE prepared_request_id=?",
                (prepared_request_id,),
            ).fetchone()
        return self._row(row)

    def reserve(self, execution_request_id, prepared_request_id,
                target, command_hash, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM external_executions WHERE prepared_request_id=?",
                (prepared_request_id,),
            ).fetchone()
            if row is not None:
                if row["target"] != target or row["command_hash"] != command_hash:
                    raise ExternalExecuteConflict(
                        "prepared_request_id associado a outro target/comando"
                    )
                con.commit()
                return self._row(row), False

            row = con.execute(
                "SELECT * FROM external_executions WHERE execution_request_id=?",
                (execution_request_id,),
            ).fetchone()
            if row is not None:
                if row["prepared_request_id"] != prepared_request_id:
                    raise ExternalExecuteConflict(
                        "execution_request_id reutilizado para outro prepared_request_id"
                    )
                con.commit()
                return self._row(row), False

            con.execute(
                "INSERT INTO external_executions(" 
                "execution_request_id,prepared_request_id,target,command_hash,state," 
                "runtime_instance,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    execution_request_id,
                    prepared_request_id,
                    target,
                    command_hash,
                    "RESERVED",
                    runtime_instance,
                    now,
                    now,
                ),
            )
            con.commit()
        return self.get_by_execution(execution_request_id), True

    def mark_executing(self, execution_request_id, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE external_executions SET state='EXECUTING',runtime_instance=?,"
                "started_at=?,updated_at=?,error_type=NULL,error_message=NULL "
                "WHERE execution_request_id=?",
                (runtime_instance, now, now, execution_request_id),
            )
        return self.get_by_execution(execution_request_id)

    def mark_finished(self, execution_request_id, output="", exit_code=0):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE external_executions SET state='FINISHED',finished_at=?,"
                "updated_at=?,output=?,exit_code=?,error_type=NULL,error_message=NULL "
                "WHERE execution_request_id=?",
                (now, now, self._cap_output(output), exit_code, execution_request_id),
            )
        return self.get_by_execution(execution_request_id)

    def mark_failed(self, execution_request_id, output="", exit_code=None,
                    error_type=None, error_message=None):
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute(
                "UPDATE external_executions SET state='FAILED',finished_at=?,"
                "updated_at=?,output=?,exit_code=?,error_type=?,error_message=? "
                "WHERE execution_request_id=?",
                (
                    now, now, self._cap_output(output), exit_code,
                    error_type, error_message, execution_request_id,
                ),
            )
        return self.get_by_execution(execution_request_id)


    @staticmethod
    def _cap_output(output):
        text = str(output or "")
        if len(text) <= MAX_FINAL_OUTPUT_CHARS:
            return text
        return text[-MAX_FINAL_OUTPUT_CHARS:]

    def append_output(self, execution_request_id, text):
        text = str(text or "")
        if not text:
            return 0
        pieces = [text[i:i + CHUNK_SIZE_CHARS] for i in range(0, len(text), CHUNK_SIZE_CHARS)]
        with self._lock, self._connect() as con:
            row = con.execute("SELECT COALESCE(MAX(seq),0) AS n FROM external_execution_chunks WHERE execution_request_id=?", (execution_request_id,)).fetchone()
            seq = int(row["n"] or 0)
            now = utc_now()
            for piece in pieces:
                seq += 1
                con.execute("INSERT INTO external_execution_chunks(execution_request_id,seq,text,created_at) VALUES(?,?,?,?)", (execution_request_id, seq, piece, now))
        return seq

    def read_output(self, execution_request_id, after_seq=0, max_chars=65536):
        after_seq = max(0, int(after_seq or 0))
        max_chars = max(1024, min(int(max_chars or 65536), 262144))
        with self._lock, self._connect() as con:
            rows = con.execute("SELECT seq,text FROM external_execution_chunks WHERE execution_request_id=? AND seq>? ORDER BY seq", (execution_request_id, after_seq)).fetchall()
        parts=[]; total=0; cursor=after_seq
        for row in rows:
            text=row["text"]
            if parts and total + len(text) > max_chars:
                break
            parts.append(text); total += len(text); cursor=int(row["seq"])
            if total >= max_chars:
                break
        return {"text": "".join(parts), "cursor": cursor, "has_more": bool(rows and cursor < int(rows[-1]["seq"]))}

    def recover_stale(self, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            cur = con.execute("UPDATE external_executions SET state='FAILED',finished_at=?,updated_at=?,error_type='ExecutionInterruptedByRestart',error_message='CodeBridge reiniciado durante execucao; comando nao sera repetido automaticamente' WHERE state IN ('RESERVED','EXECUTING') AND runtime_instance<>?", (now, now, runtime_instance))
            return int(cur.rowcount or 0)
