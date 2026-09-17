import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


VALID_STATES = {
    "CREATED", "RUNNING", "FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"
}
TERMINAL_STATES = {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}
ALLOWED_TRANSITIONS = {
    "CREATED": {"RUNNING", "CANCELLED", "INTERRUPTED"},
    "RUNNING": {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ExecutionLedgerConflict(RuntimeError):
    pass


class ExecutionLedgerStateError(RuntimeError):
    pass

class ExecutionLedger:
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
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    target TEXT NOT NULL,
                    command_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    runtime_instance TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    exit_code INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            columns = {row["name"] for row in con.execute("PRAGMA table_info(executions)")}
            if "output" not in columns:
                con.execute("ALTER TABLE executions ADD COLUMN output TEXT NOT NULL DEFAULT ''")
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_executions_state ON executions(state)"
            )
            con.execute("""
                CREATE TABLE IF NOT EXISTS execution_output_chunks (
                    execution_id TEXT NOT NULL, seq INTEGER NOT NULL,
                    start_offset INTEGER NOT NULL, text TEXT NOT NULL,
                    char_count INTEGER NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (execution_id, seq)
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_output_chunks_exec_offset "
                        "ON execution_output_chunks(execution_id,start_offset)")

    @staticmethod
    def _row(row):
        return None if row is None else dict(row)

    def get(self, execution_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
        return self._row(row)

    def get_by_request(self, request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM executions WHERE request_id=?", (request_id,)
            ).fetchone()
        return self._row(row)

    def create(self, execution_id, request_id, target, command_hash,
               runtime_instance=None):
        execution_id = str(execution_id or "").strip()
        request_id = str(request_id or "").strip()
        target = str(target or "").strip()
        command_hash = str(command_hash or "").strip()
        if not all((execution_id, request_id, target, command_hash)):
            raise ValueError("execution_id, request_id, target e command_hash obrigatorios")
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM executions WHERE execution_id=? OR request_id=?",
                (execution_id, request_id),
            ).fetchone()
            if row is not None:
                same = (
                    row["execution_id"] == execution_id
                    and row["request_id"] == request_id
                    and row["target"] == target
                    and row["command_hash"] == command_hash
                )
                if not same:
                    raise ExecutionLedgerConflict(
                        "execution_id/request_id reutilizado com dados diferentes"
                    )
                con.commit()
                return self._row(row), False
            con.execute(
                "INSERT INTO executions("
                "execution_id,request_id,target,command_hash,state,runtime_instance,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    execution_id, request_id, target, command_hash, "CREATED",
                    runtime_instance, now, now,
                ),
            )
            con.commit()
        return self.get(execution_id), True

    def transition(self, execution_id, new_state, *, runtime_instance=None,
                   exit_code=None, error_type=None, error_message=None, output=None):
        new_state = str(new_state or "").strip().upper()
        if new_state not in VALID_STATES:
            raise ValueError(f"state invalido: {new_state}")
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
            if row is None:
                raise KeyError(execution_id)
            current = row["state"]
            if new_state != current:
                allowed = ALLOWED_TRANSITIONS.get(current, set())
                if new_state not in allowed:
                    raise ExecutionLedgerStateError(
                        f"transicao invalida: {current} -> {new_state}"
                    )
            started_at = row["started_at"]
            finished_at = row["finished_at"]
            if new_state == "RUNNING" and not started_at:
                started_at = now
            if new_state in TERMINAL_STATES and not finished_at:
                finished_at = now
            if new_state == "FINISHED":
                error_type = None
                error_message = None
            stored_output = row["output"] if output is None else str(output or "")
            con.execute(
                "UPDATE executions SET state=?,runtime_instance=COALESCE(?,runtime_instance),"
                "started_at=?,finished_at=?,exit_code=?,error_type=?,error_message=?,output=?,updated_at=? "
                "WHERE execution_id=?",
                (
                    new_state, runtime_instance, started_at, finished_at, exit_code,
                    error_type, error_message, stored_output, now, execution_id,
                ),
            )
            con.commit()
        return self.get(execution_id)

    def append_output(self, execution_id, text):
        execution_id=str(execution_id or "").strip(); text=str(text or "")
        if not execution_id: raise ValueError("execution_id obrigatorio")
        if not text: return {"seq":None,"start_offset":None,"end_offset":None}
        now=utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM executions WHERE execution_id=?",(execution_id,)).fetchone() is None:
                raise KeyError(execution_id)
            meta=con.execute("SELECT COALESCE(MAX(seq),-1)+1 seq, COALESCE(MAX(start_offset+char_count),0) start_offset FROM execution_output_chunks WHERE execution_id=?",(execution_id,)).fetchone()
            seq=int(meta["seq"]); start=int(meta["start_offset"])
            con.execute("INSERT INTO execution_output_chunks(execution_id,seq,start_offset,text,char_count,created_at) VALUES(?,?,?,?,?,?)",(execution_id,seq,start,text,len(text),now))
        return {"seq":seq,"start_offset":start,"end_offset":start+len(text)}

    def sync_output(self, execution_id, output, chunk_size=16384):
        execution_id=str(execution_id or "").strip(); output=str(output or "")
        if not execution_id: raise ValueError("execution_id obrigatorio")
        chunk_size=max(1024,min(int(chunk_size or 16384),65536))
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM executions WHERE execution_id=?",(execution_id,)).fetchone() is None:
                raise KeyError(execution_id)
            meta=con.execute("SELECT COUNT(*) n, COALESCE(MAX(start_offset+char_count),0) total FROM execution_output_chunks WHERE execution_id=?",(execution_id,)).fetchone()
            if int(meta["n"]) > 0:
                return {"rewritten":False,"chars":int(meta["total"]),"reason":"append_only"}
            now=utc_now()
            for seq,start in enumerate(range(0,len(output),chunk_size)):
                text=output[start:start+chunk_size]
                con.execute("INSERT INTO execution_output_chunks(execution_id,seq,start_offset,text,char_count,created_at) VALUES(?,?,?,?,?,?)",(execution_id,seq,start,text,len(text),now))
        return {"rewritten":False,"chars":len(output),"reason":"initial_fill"}

    def read_output(self, execution_id, cursor=0, max_chars=32768):
        execution_id=str(execution_id or "").strip(); cursor=max(0,int(cursor or 0))
        max_chars=max(1,min(int(max_chars or 32768),65536))
        if not execution_id: raise ValueError("execution_id obrigatorio")
        with self._lock, self._connect() as con:
            row=con.execute("SELECT state,output FROM executions WHERE execution_id=?",(execution_id,)).fetchone()
            if row is None: raise KeyError(execution_id)
            chunks=con.execute("SELECT seq,start_offset,text,char_count FROM execution_output_chunks WHERE execution_id=? AND (start_offset+char_count)>? ORDER BY seq",(execution_id,cursor)).fetchall()
            meta=con.execute("SELECT COUNT(*) chunk_count, COALESCE(MAX(start_offset+char_count),0) total_chars FROM execution_output_chunks WHERE execution_id=?",(execution_id,)).fetchone()
        pieces=[]; remaining=max_chars; next_cursor=cursor; first_seq=None; last_seq=None
        for chunk in chunks:
            local=max(0,cursor-int(chunk["start_offset"])); part=chunk["text"][local:local+remaining]
            if part:
                if first_seq is None: first_seq=int(chunk["seq"])
                last_seq=int(chunk["seq"]); pieces.append(part); next_cursor+=len(part); remaining-=len(part)
            if remaining<=0: break
        text=''.join(pieces); total=int(meta["total_chars"])
        if int(meta["chunk_count"])==0 and (row["output"] or ""):
            legacy=row["output"] or ""; total=len(legacy); text=legacy[cursor:cursor+max_chars]; next_cursor=cursor+len(text)
        terminal=row["state"] in TERMINAL_STATES
        return {"execution_id":execution_id,"state":row["state"],"cursor":cursor,"next_cursor":next_cursor,"text":text,"chars":len(text),"available_chars":total,"first_seq":first_seq,"last_seq":last_seq,"has_more":next_cursor<total,"eof":bool(terminal and next_cursor>=total),"complete":bool(terminal)}

    def list_by_state(self, *states):
        normalized = [str(s).strip().upper() for s in states if str(s).strip()]
        if not normalized:
            return []
        invalid = [s for s in normalized if s not in VALID_STATES]
        if invalid:
            raise ValueError(f"states invalidos: {invalid}")
        marks = ",".join("?" for _ in normalized)
        with self._lock, self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM executions WHERE state IN ({marks}) ORDER BY created_at",
                tuple(normalized),
            ).fetchall()
        return [dict(row) for row in rows]

    def interrupt_incomplete_from_other_runtime(self, runtime_instance):
        now = utc_now()
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE executions SET state='INTERRUPTED',finished_at=?,updated_at=?,"
                "error_type='ExecutionInterruptedByRestart',"
                "error_message='runtime anterior terminou antes da conclusao' "
                "WHERE state IN ('CREATED','RUNNING') "
                "AND COALESCE(runtime_instance,'')<>?",
                (now, now, str(runtime_instance or "")),
            )
            return int(cur.rowcount or 0)
