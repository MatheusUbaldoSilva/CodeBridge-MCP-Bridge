import http.client
import json
import select
import socket
import threading
import time
from urllib.parse import urlsplit


class HTTPPoolResponseError(RuntimeError):
    def __init__(self, status, reason, body):
        self.status = int(status)
        self.reason = str(reason or "")
        self.body = str(body or "")
        super().__init__(
            f"HTTP {self.status}: {self.body or self.reason}"
        )


class HTTPPoolTransportError(RuntimeError):
    pass


class HTTPPoolDecodeError(RuntimeError):
    pass


class JSONHTTPConnectionPool:
    def __init__(self, max_idle_per_origin=4, max_idle_seconds=60.0):
        self.max_idle_per_origin = max(
            1, int(max_idle_per_origin)
        )
        self.max_idle_seconds = max(
            1.0, float(max_idle_seconds)
        )
        self._lock = threading.RLock()
        self._idle = {}
        self._created = 0
        self._reused = 0
        self._discarded = 0
        self._requests = 0

    @staticmethod
    def _origin(url):
        parsed = urlsplit(str(url))
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"esquema HTTP nao suportado: {parsed.scheme}"
            )
        if not parsed.hostname:
            raise ValueError("host HTTP ausente")
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return (
            parsed.scheme,
            parsed.hostname,
            int(port),
            path,
        )

    @staticmethod
    def _close(conn):
        try:
            conn.close()
        except Exception:
            pass

    @staticmethod
    def _socket_usable(conn):
        sock = getattr(conn, "sock", None)
        if sock is None:
            return False
        try:
            readable, _, _ = select.select(
                [sock], [], [], 0
            )
        except (OSError, ValueError):
            return False
        if not readable:
            return True
        try:
            data = sock.recv(1, socket.MSG_PEEK)
        except (BlockingIOError, InterruptedError):
            return True
        except OSError:
            return False
        # Readable idle sockets are closed or have unexpected data.
        return False

    def _new_connection(self, key, timeout):
        scheme, host, port = key
        cls = (
            http.client.HTTPSConnection
            if scheme == "https"
            else http.client.HTTPConnection
        )
        conn = cls(host, port, timeout=float(timeout))
        with self._lock:
            self._created += 1
        return conn

    def _acquire(self, key, timeout):
        now = time.monotonic()
        while True:
            item = None
            with self._lock:
                bucket = self._idle.get(key)
                if bucket:
                    item = bucket.pop()
                    if not bucket:
                        self._idle.pop(key, None)
            if item is None:
                return self._new_connection(key, timeout)

            conn, returned_at = item
            expired = (
                now - returned_at
                > self.max_idle_seconds
            )
            if expired or not self._socket_usable(conn):
                self._close(conn)
                with self._lock:
                    self._discarded += 1
                continue

            conn.timeout = float(timeout)
            with self._lock:
                self._reused += 1
            return conn

    def _release(self, key, conn):
        with self._lock:
            bucket = self._idle.setdefault(key, [])
            if len(bucket) >= self.max_idle_per_origin:
                self._discarded += 1
                close = True
            else:
                bucket.append((conn, time.monotonic()))
                close = False
        if close:
            self._close(conn)

    def _discard(self, conn):
        self._close(conn)
        with self._lock:
            self._discarded += 1

    def request_json(
        self,
        method,
        url,
        *,
        payload=None,
        headers=None,
        timeout=5.0,
    ):
        scheme, host, port, path = self._origin(url)
        key = (scheme, host, port)
        conn = self._acquire(key, timeout)
        body = None
        request_headers = dict(headers or {})
        request_headers.setdefault(
            "Accept", "application/json"
        )
        request_headers.setdefault(
            "Connection", "keep-alive"
        )
        if payload is not None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")
            request_headers.setdefault(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            request_headers["Content-Length"] = str(
                len(body)
            )

        with self._lock:
            self._requests += 1

        try:
            conn.request(
                str(method).upper(),
                path,
                body=body,
                headers=request_headers,
            )
            response = conn.getresponse()
            raw = response.read()
            reusable = (
                not response.will_close
                and str(
                    response.getheader("Connection", "")
                ).lower() != "close"
            )
            status = int(response.status)
            reason = str(response.reason or "")
        except (
            OSError,
            TimeoutError,
            socket.timeout,
            http.client.HTTPException,
        ) as exc:
            self._discard(conn)
            raise HTTPPoolTransportError(str(exc)) from exc

        if reusable:
            self._release(key, conn)
        else:
            self._discard(conn)

        text = raw.decode("utf-8", errors="replace")
        if status >= 400:
            raise HTTPPoolResponseError(
                status, reason, text
            )
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPPoolDecodeError(
                f"resposta JSON invalida: {exc}"
            ) from exc
        return data

    def close_all(self):
        with self._lock:
            buckets = self._idle
            self._idle = {}
        for bucket in buckets.values():
            for conn, _ in bucket:
                self._close(conn)

    def stats(self):
        with self._lock:
            return {
                "created": self._created,
                "reused": self._reused,
                "discarded": self._discarded,
                "requests": self._requests,
                "idle": sum(
                    len(bucket)
                    for bucket in self._idle.values()
                ),
            }


SHARED_HTTP_POOL = JSONHTTPConnectionPool()