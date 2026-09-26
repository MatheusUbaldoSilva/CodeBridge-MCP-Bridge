import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


COMPANION_HOST = "127.0.0.1"
COMPANION_PORT = 8768
COMPANION_HEADER = "X-CodeBridge-Companion"
COMPANION_HEADER_VALUE = "chatgpt-timer-v1"
PREPARE_WRAP_UP_SECONDS = 16 * 60 + 30
WRAP_UP_SECONDS = 17 * 60


class ChatGPTTimerState:
    VALID_STATES = {
        "IDLE",
        "RUNNING",
        "FINISHED",
        "CANCELLED",
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._state = "IDLE"
        self._request_id = None
        self._started_monotonic = None
        self._finished_monotonic = None
        self._started_at = None
        self._finished_at = None
        self._manual_wrap_up_requested = False
        self._manual_wrap_up_reason = None
        self._manual_wrap_up_requested_at = None

    def _snapshot_locked(self):
        elapsed = 0.0

        if self._started_monotonic is not None:
            end = (
                time.monotonic()
                if self._state == "RUNNING"
                else (
                    self._finished_monotonic
                    if self._finished_monotonic is not None
                    else time.monotonic()
                )
            )
            elapsed = max(
                0.0,
                end - self._started_monotonic,
            )

        return {
            "state": self._state,
            "request_id": self._request_id,
            "elapsed_seconds": elapsed,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def turn_control(self):
        with self._lock:
            timer = self._snapshot_locked()

        elapsed = float(
            timer.get("elapsed_seconds") or 0.0
        )
        running = (
            timer.get("state") == "RUNNING"
        )

        with self._lock:
            manual_requested = bool(
                self._manual_wrap_up_requested
            )
            manual_reason = (
                self._manual_wrap_up_reason
            )
            manual_requested_at = (
                self._manual_wrap_up_requested_at
            )

        if manual_requested:
            stage = "WRAP_UP_NOW"
            action = "FINISH_RESPONSE_NORMALLY"
            remaining = 0.0
            directive = (
                "A manual graceful stop was requested in CodeBridge. "
                "Let the current command finish normally. "
                "Do not start any new command or long-running step. "
                "Collect the current command result, summarize the "
                "exact point reached, completed work, current state, "
                "pending work, and the next step. "
                "Ask the user to send 'continuar'. "
                "Do not cancel the current command and do not stop "
                "the ChatGPT generation."
            )

        elif not running:
            stage = "INACTIVE"
            action = "NONE"
            remaining = None
            directive = (
                "No turn wrap-up is requested."
            )

        elif elapsed >= WRAP_UP_SECONDS:
            stage = "WRAP_UP_NOW"
            action = "FINISH_RESPONSE_NORMALLY"
            remaining = 0.0
            directive = (
                "Finish the current assistant response normally. "
                "Do not start another long-running step. "
                "Summarize the exact point reached, completed work, "
                "current state, pending work, and the next step. "
                "Ask the user to send 'continuar'. "
                "Do not cancel or stop the ChatGPT generation."
            )

        elif elapsed >= PREPARE_WRAP_UP_SECONDS:
            stage = "PREPARE_WRAP_UP"
            action = "PREPARE_CHECKPOINT"
            remaining = max(
                0.0,
                WRAP_UP_SECONDS - elapsed,
            )
            directive = (
                "Prepare to close this assistant turn normally. "
                "Avoid starting a new long-running step. "
                "Finish the current atomic operation and be ready "
                "to provide a checkpoint."
            )

        else:
            stage = "NORMAL"
            action = "CONTINUE"
            remaining = max(
                0.0,
                WRAP_UP_SECONDS - elapsed,
            )
            directive = (
                "Continue the current work normally."
            )

        return {
            "stage": stage,
            "action": action,
            "request_wrap_up": (
                stage == "WRAP_UP_NOW"
            ),
            "elapsed_seconds": elapsed,
            "prepare_wrap_up_seconds":
                PREPARE_WRAP_UP_SECONDS,
            "wrap_up_seconds": WRAP_UP_SECONDS,
            "remaining_seconds": remaining,
            "request_id": timer.get("request_id"),
            "manual_request": manual_requested,
            "reason": (
                manual_reason
                if manual_requested
                else (
                    "time_limit"
                    if stage in (
                        "PREPARE_WRAP_UP",
                        "WRAP_UP_NOW",
                    )
                    else None
                )
            ),
            "manual_requested_at":
                manual_requested_at,
            "directive": directive,
        }

    def request_manual_wrap_up(
        self,
        reason="manual_stop_button",
    ):
        with self._lock:
            already_requested = bool(
                self._manual_wrap_up_requested
            )
            if not already_requested:
                self._manual_wrap_up_requested = True
                self._manual_wrap_up_reason = str(
                    reason or "manual_stop_button"
                )
                self._manual_wrap_up_requested_at = (
                    time.time()
                )

            return {
                "applied": not already_requested,
                "turn_control": self.turn_control(),
            }

    def start(
        self,
        request_id,
        resume_manual=False,
    ):
        request_id = str(request_id or "").strip()

        if not request_id:
            raise ValueError("request_id obrigatorio")

        with self._lock:
            if (
                self._state == "RUNNING"
                and self._request_id == request_id
            ):
                return {
                    "applied": False,
                    "timer": self._snapshot_locked(),
                }

            now_monotonic = time.monotonic()

            if resume_manual:
                self._manual_wrap_up_requested = False
                self._manual_wrap_up_reason = None
                self._manual_wrap_up_requested_at = None

            self._state = "RUNNING"
            self._request_id = request_id
            self._started_monotonic = now_monotonic
            self._finished_monotonic = None
            self._started_at = time.time()
            self._finished_at = None

            return {
                "applied": True,
                "timer": self._snapshot_locked(),
            }

    def _finish(self, request_id, state):
        request_id = str(request_id or "").strip()

        if state not in ("FINISHED", "CANCELLED"):
            raise ValueError("estado final invalido")

        with self._lock:
            if self._state != "RUNNING":
                return {
                    "applied": False,
                    "timer": self._snapshot_locked(),
                }

            if (
                request_id
                and request_id != self._request_id
            ):
                return {
                    "applied": False,
                    "timer": self._snapshot_locked(),
                }

            self._state = state
            self._finished_monotonic = time.monotonic()
            self._finished_at = time.time()

            return {
                "applied": True,
                "timer": self._snapshot_locked(),
            }

    def finish(self, request_id=None):
        return self._finish(
            request_id,
            "FINISHED",
        )

    def cancel(self, request_id=None):
        return self._finish(
            request_id,
            "CANCELLED",
        )

    def reset(self):
        with self._lock:
            self._state = "IDLE"
            self._request_id = None
            self._started_monotonic = None
            self._finished_monotonic = None
            self._started_at = None
            self._finished_at = None
            self._manual_wrap_up_requested = False
            self._manual_wrap_up_reason = None
            self._manual_wrap_up_requested_at = None

            return {
                "applied": True,
                "timer": self._snapshot_locked(),
            }


class ChatGPTCompanionServer:
    def __init__(
        self,
        timer,
        host=COMPANION_HOST,
        port=COMPANION_PORT,
    ):
        self.timer = timer
        self.host = host
        self.port = int(port)
        self._server = None
        self._thread = None

    @property
    def running(self):
        return bool(
            self._thread is not None
            and self._thread.is_alive()
        )

    def start(self):
        if self.running:
            return False

        companion = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CodeBridgeCompanion/1.0"

            def log_message(self, fmt, *args):
                return

            def _authorized(self):
                return (
                    self.headers.get(
                        COMPANION_HEADER,
                        "",
                    )
                    == COMPANION_HEADER_VALUE
                )

            def _send(self, status, payload):
                body = json.dumps(
                    payload,
                    ensure_ascii=False,
                ).encode("utf-8")

                self.send_response(status)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )
                self.send_header(
                    "Cache-Control",
                    "no-store",
                )
                self.end_headers()
                self.wfile.write(body)

            def _json_body(self):
                length = int(
                    self.headers.get(
                        "Content-Length",
                        "0",
                    )
                    or 0
                )
                raw = (
                    self.rfile.read(length)
                    if length
                    else b"{}"
                )
                data = json.loads(
                    raw.decode("utf-8")
                )
                if not isinstance(data, dict):
                    raise ValueError(
                        "body deve ser objeto JSON"
                    )
                return data

            def _guard(self):
                if self._authorized():
                    return True

                self._send(
                    403,
                    {
                        "ok": False,
                        "error": "forbidden",
                    },
                )
                return False

            def do_GET(self):
                path = urlparse(
                    self.path
                ).path

                if path == "/healthz":
                    return self._send(
                        200,
                        {
                            "ok": True,
                            "service": "chatgpt-companion",
                        },
                    )

                if not self._guard():
                    return

                if path == "/v1/chatgpt/timer":
                    return self._send(
                        200,
                        {
                            "ok": True,
                            "timer": companion.timer.snapshot(),
                        },
                    )

                self._send(
                    404,
                    {
                        "ok": False,
                        "error": "not_found",
                    },
                )

            def do_POST(self):
                if not self._guard():
                    return

                path = urlparse(
                    self.path
                ).path

                try:
                    body = self._json_body()
                    request_id = body.get(
                        "request_id"
                    )

                    if path == "/v1/chatgpt/timer/start":
                        result = companion.timer.start(
                            request_id,
                            resume_manual=bool(
                                body.get(
                                    "resume_manual",
                                    False,
                                )
                            ),
                        )
                    elif path == "/v1/chatgpt/timer/finish":
                        result = companion.timer.finish(
                            request_id
                        )
                    elif path == "/v1/chatgpt/timer/cancel":
                        result = companion.timer.cancel(
                            request_id
                        )
                    elif path == "/v1/chatgpt/timer/reset":
                        result = companion.timer.reset()
                    else:
                        return self._send(
                            404,
                            {
                                "ok": False,
                                "error": "not_found",
                            },
                        )

                    return self._send(
                        200,
                        {
                            "ok": True,
                            **result,
                        },
                    )

                except Exception as exc:
                    self._send(
                        400,
                        {
                            "ok": False,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        },
                    )

        self._server = ThreadingHTTPServer(
            (
                self.host,
                self.port,
            ),
            Handler,
        )
        self.port = int(
            self._server.server_address[1]
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="CodeBridgeChatGPTCompanion",
            daemon=True,
        )
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

        if (
            thread is not None
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=3
            )

        return True
