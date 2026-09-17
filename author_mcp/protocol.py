import hashlib
import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone


PROTOCOL_VERSION = "CBMCP/1"


class ProtocolError(RuntimeError):
    pass


class ProtocolConflict(ProtocolError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_payload(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


class ProtocolLedger:
    """Ledger em memória para validar a semântica antes da integração persistente."""

    def __init__(self):
        self._lock = threading.RLock()
        self._requests = {}

    def receive_request_syn(self, operation, payload, request_id=None):
        request_id = request_id or new_id("req")
        request_hash = sha256_payload(payload)
        with self._lock:
            current = self._requests.get(request_id)
            if current is not None:
                if current["request_hash"] != request_hash or current["operation"] != operation:
                    raise ProtocolConflict("request_id reutilizado com conteúdo diferente")
                return deepcopy(current["request_ack"])

            ack = {
                "protocol": PROTOCOL_VERSION,
                "type": "REQUEST_ACK",
                "request_id": request_id,
                "request_hash": request_hash,
                "operation": operation,
                "acked_at": utc_now(),
            }
            self._requests[request_id] = {
                "state": "REQUEST_ACKED",
                "operation": operation,
                "payload": deepcopy(payload),
                "request_hash": request_hash,
                "request_ack": ack,
                "response_syn": None,
                "response_ack": None,
            }
            return deepcopy(ack)

    def prepare_response(self, request_id, payload):
        response_hash = sha256_payload(payload)
        with self._lock:
            current = self._requests.get(request_id)
            if current is None:
                raise ProtocolError("request_id desconhecido")
            existing = current["response_syn"]
            if existing is not None:
                if existing["response_hash"] != response_hash:
                    raise ProtocolConflict("resposta já preparada com conteúdo diferente")
                return deepcopy(existing)

            syn = {
                "protocol": PROTOCOL_VERSION,
                "type": "RESPONSE_SYN",
                "request_id": request_id,
                "response_id": new_id("res"),
                "response_hash": response_hash,
                "payload": deepcopy(payload),
                "created_at": utc_now(),
            }
            current["state"] = "RESPONSE_READY"
            current["response_syn"] = syn
            return deepcopy(syn)

    def receive_response_ack(self, request_id, response_id, response_hash):
        with self._lock:
            current = self._requests.get(request_id)
            if current is None or current["response_syn"] is None:
                raise ProtocolError("resposta ainda não existe")
            syn = current["response_syn"]
            if syn["response_id"] != response_id or syn["response_hash"] != response_hash:
                raise ProtocolConflict("ACK de resposta não corresponde ao RESPONSE_SYN")
            if current["response_ack"] is None:
                current["response_ack"] = {
                    "protocol": PROTOCOL_VERSION,
                    "type": "RESPONSE_ACK",
                    "request_id": request_id,
                    "response_id": response_id,
                    "response_hash": response_hash,
                    "acked_at": utc_now(),
                }
                current["state"] = "RESPONSE_ACKED"
            return deepcopy(current["response_ack"])

    def get_exchange(self, request_id):
        with self._lock:
            current = self._requests.get(request_id)
            if current is None:
                raise ProtocolError("request_id desconhecido")
            return deepcopy(current)

    def count(self):
        with self._lock:
            return len(self._requests)


def validate_request_ack(request_syn, request_ack):
    expected_hash = sha256_payload(request_syn["payload"])
    if request_ack.get("type") != "REQUEST_ACK":
        raise ProtocolError("REQUEST_ACK ausente")
    if request_ack.get("request_id") != request_syn.get("request_id"):
        raise ProtocolError("request_id divergente no ACK")
    if request_ack.get("request_hash") != expected_hash:
        raise ProtocolError("request_hash divergente no ACK")
    return True


def validate_response_syn(request_id, response_syn):
    if response_syn.get("type") != "RESPONSE_SYN" or response_syn.get("request_id") != request_id:
        raise ProtocolError("RESPONSE_SYN inválido")
    if response_syn.get("response_hash") != sha256_payload(response_syn.get("payload")):
        raise ProtocolError("response_hash inválido")
    return True
