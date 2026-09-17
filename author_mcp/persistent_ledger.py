import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from protocol import (
    PROTOCOL_VERSION,
    ProtocolConflict,
    ProtocolError,
    canonical_json,
    new_id,
    sha256_payload,
    utc_now,
)


class PersistentProtocolLedger:
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
        finally:
            con.close()

    def _initialize(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS exchanges (
                    request_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    request_payload TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    request_ack TEXT NOT NULL,
                    response_id TEXT,
                    response_payload TEXT,
                    response_hash TEXT,
                    response_syn TEXT,
                    response_ack TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _loads(value):
        return None if value is None else json.loads(value)

    def receive_request_syn(self, operation, payload, request_id=None):
        request_id = request_id or new_id("req")
        request_hash = sha256_payload(payload)
        request_ack = {
            "protocol": PROTOCOL_VERSION,
            "type": "REQUEST_ACK",
            "request_id": request_id,
            "request_hash": request_hash,
            "operation": operation,
            "acked_at": utc_now(),
        }
        now = utc_now()
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM exchanges WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash or row["operation"] != operation:
                    raise ProtocolConflict("request_id reutilizado com conteúdo diferente")
                con.commit()
                return self._loads(row["request_ack"])
            con.execute(
                "INSERT INTO exchanges(request_id,operation,request_payload,request_hash,state,request_ack,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    operation,
                    canonical_json(payload),
                    request_hash,
                    "REQUEST_ACKED",
                    canonical_json(request_ack),
                    now,
                    now,
                ),
            )
            con.commit()
        return request_ack

    def prepare_response(self, request_id, payload):
        response_hash = sha256_payload(payload)
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM exchanges WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None:
                raise ProtocolError("request_id desconhecido")
            if row["response_syn"] is not None:
                if row["response_hash"] != response_hash:
                    raise ProtocolConflict("resposta já preparada com conteúdo diferente")
                con.commit()
                return self._loads(row["response_syn"])

            response_syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "RESPONSE_SYN",
                "request_id": request_id,
                "response_id": new_id("res"),
                "response_hash": response_hash,
                "payload": payload,
                "created_at": utc_now(),
            }
            con.execute(
                "UPDATE exchanges SET state='RESPONSE_READY',response_id=?,response_payload=?,response_hash=?,response_syn=?,updated_at=? WHERE request_id=?",
                (
                    response_syn["response_id"],
                    canonical_json(payload),
                    response_hash,
                    canonical_json(response_syn),
                    utc_now(),
                    request_id,
                ),
            )
            con.commit()
        return response_syn

    def get_response_syn(self, request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT response_syn FROM exchanges WHERE request_id=?", (request_id,)
            ).fetchone()
        if row is None:
            raise ProtocolError("request_id desconhecido")
        return self._loads(row["response_syn"])

    def receive_response_ack(self, request_id, response_id, response_hash):
        with self._lock, self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM exchanges WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None or row["response_syn"] is None:
                raise ProtocolError("resposta ainda não existe")
            if row["response_id"] != response_id or row["response_hash"] != response_hash:
                raise ProtocolConflict("ACK de resposta não corresponde ao RESPONSE_SYN")
            if row["response_ack"] is not None:
                con.commit()
                return self._loads(row["response_ack"])
            response_ack = {
                "protocol": PROTOCOL_VERSION,
                "type": "RESPONSE_ACK",
                "request_id": request_id,
                "response_id": response_id,
                "response_hash": response_hash,
                "acked_at": utc_now(),
            }
            con.execute(
                "UPDATE exchanges SET state='RESPONSE_ACKED',response_ack=?,updated_at=? WHERE request_id=?",
                (canonical_json(response_ack), utc_now(), request_id),
            )
            con.commit()
        return response_ack

    def get_exchange(self, request_id):
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT * FROM exchanges WHERE request_id=?", (request_id,)
            ).fetchone()
        if row is None:
            raise ProtocolError("request_id desconhecido")
        result = dict(row)
        for key in ("request_payload", "request_ack", "response_payload", "response_syn", "response_ack"):
            result[key] = self._loads(result[key])
        return result

    def count(self):
        with self._lock, self._connect() as con:
            return int(con.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0])
