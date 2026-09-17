import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from persistent_ledger import PersistentProtocolLedger
from protocol import PROTOCOL_VERSION, ProtocolConflict, ProtocolError, sha256_payload
from runtime_client import (
    codebridge_discard, codebridge_dispatch, codebridge_execute_prepared,
    codebridge_execution_status, codebridge_prepare, codebridge_start_async,
    codebridge_status, codebridge_stop, codebridge_v2_output, codebridge_v2_result,
    codebridge_v2_start, codebridge_v2_status, codebridge_v2_stop,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
LEDGER_FILE = DATA_DIR / "author_mcp_protocol.db"


class AdapterState:
    def __init__(self, ledger_path=LEDGER_FILE, operations=None):
        self.ledger = PersistentProtocolLedger(ledger_path)
        self.operations = operations or {
            "STATUS": lambda payload, request_id=None: codebridge_status(),
            "PREPARE": lambda payload, request_id=None: codebridge_prepare(
                request_id, payload.get("target"), payload.get("command")
            ),
            "DISCARD": lambda payload, request_id=None: codebridge_discard(
                payload.get("request_id")
            ),
            "DISPATCH": lambda payload, request_id=None: codebridge_dispatch(
                request_id, payload.get("target"), payload.get("command")
            ),
            "EXECUTE_PREPARED": lambda payload, request_id=None: codebridge_execute_prepared(
                request_id, payload.get("prepared_request_id")
            ),
            "STOP": lambda payload, request_id=None: codebridge_stop(),
            "START_ASYNC": lambda payload, request_id=None: codebridge_start_async(
                request_id, payload.get("target"), payload.get("command")
            ),
            "EXECUTION_STATUS": lambda payload, request_id=None: codebridge_execution_status(
                payload.get("execution_id"), payload.get("cursor", 0),
                payload.get("max_chars", 65536)
            ),
            "EXECUTION_V2_START": lambda payload, request_id=None: codebridge_v2_start(
                request_id, payload.get("target"), payload.get("command")
            ),
            "EXECUTION_V2_STATUS": lambda payload, request_id=None: codebridge_v2_status(
                payload.get("execution_id")
            ),
            "EXECUTION_V2_RESULT": lambda payload, request_id=None: codebridge_v2_result(
                payload.get("execution_id")
            ),
            "EXECUTION_V2_OUTPUT": lambda payload, request_id=None: codebridge_v2_output(
                payload.get("execution_id"), payload.get("cursor", 0),
                payload.get("max_chars", 32768)
            ),
            "EXECUTION_V2_STOP": lambda payload, request_id=None: codebridge_v2_stop(
                payload.get("execution_id")
            ),
        }
        self._operation_lock = threading.RLock()
        self._request_locks = {}

    def _validate_request_syn(self, body):
        if body.get("protocol") != PROTOCOL_VERSION or body.get("type") != "REQUEST_SYN":
            raise ProtocolError("REQUEST_SYN invalido")
        payload = body.get("payload")
        if not isinstance(payload, dict):
            raise ProtocolError("payload deve ser objeto")
        if body.get("request_hash") != sha256_payload(payload):
            raise ProtocolError("request_hash invalido")
        if body.get("operation") not in self.operations:
            raise ProtocolError("operacao nao permitida")
        if not body.get("request_id"):
            raise ProtocolError("request_id ausente")
        return payload

    def receive_request(self, body):
        payload = self._validate_request_syn(body)
        request_id = body["request_id"]
        operation = body["operation"]
        return self.ledger.receive_request_syn(
            operation, payload, request_id=request_id
        )

    def _request_lock(self, request_id):
        with self._operation_lock:
            lock = self._request_locks.get(request_id)
            if lock is None:
                lock = threading.RLock()
                self._request_locks[request_id] = lock
            return lock

    def response_syn(self, request_id):
        with self._request_lock(request_id):
            response = self.ledger.get_response_syn(request_id)
            if response is not None:
                return response
            exchange = self.ledger.get_exchange(request_id)
            operation = exchange["operation"]
            payload = exchange["request_payload"]
            try:
                result = self.operations[operation](payload, request_id=request_id)
                if isinstance(result, dict):
                    result = dict(result)
                    result.setdefault("operation_ok", True)
            except Exception as exc:
                result = {
                    "operation_ok": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "retriable": False,
                }
            return self.ledger.prepare_response(request_id, result)

    def response_ack(self, body):
        if body.get("protocol") != PROTOCOL_VERSION or body.get("type") != "RESPONSE_ACK":
            raise ProtocolError("RESPONSE_ACK invalido")
        return self.ledger.receive_response_ack(
            body.get("request_id"), body.get("response_id"), body.get("response_hash")
        )


def make_server(host=DEFAULT_HOST, port=DEFAULT_PORT, state=None):
    state = state or AdapterState()

    class Handler(BaseHTTPRequestHandler):
        server_version = "CodeBridgeAuthorAdapter/0.1"

        def log_message(self, fmt, *args):
            return

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ProtocolError("body deve ser objeto JSON")
            return data

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {
                    "ok": True,
                    "protocol": PROTOCOL_VERSION,
                    "pid": os.getpid(),
                    "operations": sorted(state.operations),
                })
            return self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            try:
                body = self._read_json()
                if self.path == "/v1/request-syn":
                    ack = state.receive_request(body)
                    return self._send(200, {"ok": True, "request_ack": ack})
                if self.path == "/v1/response-syn":
                    syn = state.response_syn(body.get("request_id"))
                    return self._send(200, {"ok": True, "response_syn": syn})
                if self.path == "/v1/response-ack":
                    ack = state.response_ack(body)
                    return self._send(200, {"ok": True, "response_ack": ack})
                return self._send(404, {"ok": False, "error": "not_found"})
            except ProtocolConflict as exc:
                return self._send(409, {"ok": False, "error": type(exc).__name__, "message": str(exc)})
            except (ProtocolError, ValueError, json.JSONDecodeError) as exc:
                return self._send(400, {"ok": False, "error": type(exc).__name__, "message": str(exc)})
            except Exception as exc:
                return self._send(503, {"ok": False, "error": type(exc).__name__, "message": str(exc)})

    return ThreadingHTTPServer((host, int(port)), Handler)


def serve(host=DEFAULT_HOST, port=DEFAULT_PORT):
    server = make_server(host=host, port=port)
    print(f"CodeBridge author adapter ONLINE http://{host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
