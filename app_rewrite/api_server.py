import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class BridgeAPI:
    def __init__(self, runtime, host="127.0.0.1", port=0, token=None):
        self.runtime = runtime
        self.host = host
        self.port = int(port)
        self.token = token
        self._server = None
        self._thread = None

    @property
    def running(self):
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self):
        if self.running:
            return False
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CodeBridgeMCP/2.0"
            def log_message(self, fmt, *args):
                return

            def _authorized(self):
                return self.headers.get("Authorization", "") == f"Bearer {bridge.token}"

            def _json_body(self):
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("body deve ser objeto JSON")
                return data

            def _send(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _guard(self):
                if self._authorized():
                    return True
                self._send(401, {"ok": False, "error": "unauthorized"})
                return False

            def do_GET(self):
                if not self._guard():
                    return
                path = urlparse(self.path).path
                try:
                    if path == "/v1/status":
                        return self._send(200, {"ok": True, "status": bridge.runtime.snapshot()})
                    if path == "/v1/ssh/config":
                        return self._send(200, {"ok": True, "ssh": bridge.runtime.terminals.ssh_settings()})
                    if path.startswith("/v1/phase5f/executions/") and path.endswith("/output"):
                        parts = path.strip("/").split("/")
                        if len(parts) != 5:
                            return self._send(404, {"ok": False, "error": "not_found"})
                        query = parse_qs(urlparse(self.path).query)
                        cursor = int((query.get("cursor") or [0])[0])
                        max_chars = int((query.get("max_chars") or [32768])[0])
                        result = bridge.runtime.phase5f_execution_output(
                            parts[3], cursor=cursor, max_chars=max_chars
                        )
                        return self._send(200, {"ok": True, "output": result})
                    if path.startswith("/v1/phase5c/executions/"):
                        parts = path.strip("/").split("/")
                        if len(parts) == 4:
                            result = bridge.runtime.phase5c_execution_status(parts[3])
                            return self._send(200, {"ok": True, "execution": result})
                        if len(parts) == 5 and parts[4] == "result":
                            result = bridge.runtime.phase5c_execution_result(parts[3])
                            return self._send(200, {"ok": True, "result": result})
                        return self._send(404, {"ok": False, "error": "not_found"})
                    if path.startswith("/v1/executions/"):
                        execution_id = path.rsplit("/", 1)[-1]
                        query = parse_qs(urlparse(self.path).query)
                        cursor = int((query.get("cursor") or [0])[0])
                        max_chars = int((query.get("max_chars") or [65536])[0])
                        result = bridge.runtime.execution_status_external(execution_id, cursor, max_chars)
                        return self._send(200, {"ok": True, "execution": result})
                    if path.startswith("/v1/jobs/"):
                        job_id = path.rsplit("/", 1)[-1]
                        return self._send(200, {"ok": True, "job": bridge.runtime.store.get(job_id)})
                    self._send(404, {"ok": False, "error": "not_found"})
                except KeyError:
                    error = "execution_not_found" if path.startswith(("/v1/phase5c/executions/", "/v1/phase5f/executions/")) else "job_not_found"
                    self._send(404, {"ok": False, "error": error})
                except Exception as exc:
                    self._send(400, {"ok": False, "error": type(exc).__name__, "message": str(exc)})

            def do_POST(self):
                if not self._guard():
                    return
                path = urlparse(self.path).path
                try:
                    body = self._json_body()
                    if path == "/v1/jobs":
                        job = bridge.runtime.submit(body.get("target"), body.get("command"))
                        return self._send(201, {"ok": True, "job": job})
                    if path == "/v1/stop":
                        return self._send(200, {"ok": True, "cancelled": bridge.runtime.stop_active()})
                    if path == "/v1/settings/auto":
                        enabled = bridge.runtime.set_auto_execute(bool(body.get("enabled")))
                        return self._send(200, {"ok": True, "auto_execute": enabled})
                    if path == "/v1/terminal/prepare":
                        prepared = bridge.runtime.prepare_external(
                            body.get("request_id"), body.get("target"), body.get("command")
                        )
                        return self._send(200, {"ok": True, "prepared": prepared})
                    if path == "/v1/terminal/dispatch":
                        result = bridge.runtime.dispatch_external(
                            body.get("request_id"), body.get("target"), body.get("command")
                        )
                        return self._send(200, {"ok": True, "dispatch": result})
                    if path == "/v1/executions/start":
                        result = bridge.runtime.start_external_async(
                            body.get("request_id"), body.get("target"), body.get("command")
                        )
                        return self._send(202, {"ok": True, "dispatch": result})
                    if path == "/v1/phase5b/start":
                        result = bridge.runtime.start_phase5b_local(
                            body.get("request_id"), body.get("target"), body.get("command")
                        )
                        return self._send(202, {"ok": True, "execution": result})
                    if path.startswith("/v1/phase5d/executions/") and path.endswith("/stop"):
                        parts = path.strip("/").split("/")
                        if len(parts) != 5:
                            return self._send(404, {"ok": False, "error": "not_found"})
                        result = bridge.runtime.stop_phase5d_execution(parts[3])
                        return self._send(200, {"ok": True, "stop": result})
                    if path == "/v1/terminal/discard":
                        result = bridge.runtime.discard_external(body.get("request_id"))
                        return self._send(200, {"ok": True, "result": result})
                    if path == "/v1/terminal/execute-prepared":
                        result = bridge.runtime.execute_external(
                            body.get("execution_request_id"),
                            body.get("prepared_request_id"),
                        )
                        return self._send(200, {"ok": True, "execution": result})
                    if path.startswith("/v1/jobs/") and path.endswith("/approve"):
                        job_id = path.split("/")[3]
                        job = bridge.runtime.approve(job_id)
                        return self._send(200, {"ok": True, "job": job})
                    if path.startswith("/v1/jobs/") and path.endswith("/cancel"):
                        job_id = path.split("/")[3]
                        cancelled = bridge.runtime.cancel(job_id)
                        return self._send(200, {"ok": True, "cancelled": cancelled})
                    if path == "/v1/ssh/test":
                        ok = bridge.runtime.terminals.test_ssh(
                            body.get("host"), body.get("port", 22),
                            body.get("username"), body.get("password"),
                        )
                        return self._send(200, {"ok": True, "ssh": {"connected": bool(ok)}})
                    if path == "/v1/ssh/config":
                        ssh = bridge.runtime.terminals.configure_ssh(
                            body.get("host"), body.get("port", 22),
                            body.get("username"), body.get("password"),
                        )
                        return self._send(200, {"ok": True, "ssh": ssh})
                    self._send(404, {"ok": False, "error": "not_found"})
                except KeyError:
                    error = "execution_not_found" if path.startswith("/v1/phase5d/executions/") else "job_not_found"
                    self._send(404, {"ok": False, "error": error})
                except Exception as exc:
                    self._send(400, {"ok": False, "error": type(exc).__name__, "message": str(exc)})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, name="CodeBridgeMCPAPI", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3)
        return True
