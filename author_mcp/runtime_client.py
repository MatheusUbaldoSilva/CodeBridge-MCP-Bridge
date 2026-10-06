import json
import os
import threading
from pathlib import Path
from urllib.parse import quote, urlencode

from http_pool import (
    HTTPPoolDecodeError,
    HTTPPoolResponseError,
    HTTPPoolTransportError,
    SHARED_HTTP_POOL,
)


DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
RUNTIME_FILE = DATA_DIR / "runtime.json"

_RUNTIME_CACHE_LOCK = threading.RLock()
_RUNTIME_CACHE_SIGNATURE = None
_RUNTIME_CACHE_VALUE = None


class CodeBridgeUnavailable(RuntimeError):
    pass


class CodeBridgeRequestError(RuntimeError):
    pass


def _http_error_message(exc):
    raw = str(getattr(exc, "body", "") or "")
    status = int(getattr(exc, "status", 0) or 0)
    reason = str(getattr(exc, "reason", "") or "")
    if raw:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            detail = (
                payload.get("message")
                or payload.get("error")
                or raw
            )
            return f"HTTP {status}: {detail}"
        return f"HTTP {status}: {raw}"
    return f"HTTP {status}: {reason}"


def _runtime_file_signature():
    try:
        stat = RUNTIME_FILE.stat()
    except FileNotFoundError as exc:
        _invalidate_runtime_cache()
        raise CodeBridgeUnavailable(
            "runtime.json nao encontrado"
        ) from exc
    return (
        int(getattr(stat, "st_ino", 0) or 0),
        int(stat.st_size),
        int(stat.st_mtime_ns),
    )


def _invalidate_runtime_cache():
    global _RUNTIME_CACHE_SIGNATURE, _RUNTIME_CACHE_VALUE
    with _RUNTIME_CACHE_LOCK:
        _RUNTIME_CACHE_SIGNATURE = None
        _RUNTIME_CACHE_VALUE = None


def _read_runtime_file():
    try:
        data = json.loads(
            RUNTIME_FILE.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        _invalidate_runtime_cache()
        raise CodeBridgeUnavailable(
            "runtime.json nao encontrado"
        ) from exc
    for key in ("host", "port", "token"):
        if not data.get(key):
            raise CodeBridgeUnavailable(
                f"runtime.json sem {key}"
            )
    return data


def _load_runtime():
    global _RUNTIME_CACHE_SIGNATURE, _RUNTIME_CACHE_VALUE
    signature = _runtime_file_signature()
    with _RUNTIME_CACHE_LOCK:
        if (
            _RUNTIME_CACHE_VALUE is not None
            and _RUNTIME_CACHE_SIGNATURE == signature
        ):
            return dict(_RUNTIME_CACHE_VALUE)

    data = _read_runtime_file()
    final_signature = _runtime_file_signature()
    if final_signature != signature:
        data = _read_runtime_file()
        final_signature = _runtime_file_signature()

    with _RUNTIME_CACHE_LOCK:
        _RUNTIME_CACHE_SIGNATURE = final_signature
        _RUNTIME_CACHE_VALUE = dict(data)
        return dict(_RUNTIME_CACHE_VALUE)


def _get_json(url, token, timeout=3.0):
    try:
        return SHARED_HTTP_POOL.request_json(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {token}"
            },
            timeout=timeout,
        )
    except HTTPPoolResponseError as exc:
        raise CodeBridgeRequestError(
            _http_error_message(exc)
        ) from exc
    except HTTPPoolDecodeError as exc:
        raise CodeBridgeRequestError(str(exc)) from exc
    except HTTPPoolTransportError as exc:
        raise CodeBridgeUnavailable(str(exc)) from exc


def _post_json(url, token, payload, timeout=5.0):
    try:
        return SHARED_HTTP_POOL.request_json(
            "POST",
            url,
            payload=payload,
            headers={
                "Authorization": f"Bearer {token}"
            },
            timeout=timeout,
        )
    except HTTPPoolResponseError as exc:
        raise CodeBridgeRequestError(
            _http_error_message(exc)
        ) from exc
    except HTTPPoolDecodeError as exc:
        raise CodeBridgeRequestError(str(exc)) from exc
    except HTTPPoolTransportError as exc:
        raise CodeBridgeUnavailable(str(exc)) from exc


def codebridge_status():
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/status"
    payload = _get_json(url, runtime["token"])
    status = payload.get("status") or {}
    terminals = status.get("terminals") or {}
    return {
        "app": status.get("app"),
        "version": status.get("version"),
        "overall": status.get("overall"),
        "api_online": bool((status.get("api") or {}).get("online")),
        "terminals": {
            "powershell": terminals.get("powershell"),
            "cmd": terminals.get("cmd"),
            "ssh": terminals.get("ssh"),
            "active_target": terminals.get("active_target"),
            "prepared_target": terminals.get("prepared_target"),
            "execution_generation": terminals.get(
                "execution_generation"
            ),
            "last_execution_target": terminals.get(
                "last_execution_target"
            ),
        },
        "queue": status.get("queue"),
        "executor": status.get("executor"),
        "auto_execute": bool(status.get("auto_execute")),
        "completion_sound": status.get(
            "completion_sound"
        ),
        "turn_control": status.get("turn_control"),
    }


def codebridge_turn_control():
    runtime = _load_runtime()
    url = (
        f"http://{runtime['host']}:"
        f"{int(runtime['port'])}/v1/status"
    )
    payload = _get_json(
        url,
        runtime["token"],
        timeout=3.0,
    )
    status = payload.get("status") or {}
    control = status.get("turn_control")
    if isinstance(control, dict):
        return dict(control)
    return {
        "stage": "INACTIVE",
        "action": "NONE",
        "request_wrap_up": False,
        "directive": "No turn wrap-up is requested.",
    }


def codebridge_prepare(request_id, target, command):
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/terminal/prepare"
    payload = _post_json(url, runtime["token"], {
        "request_id": request_id,
        "target": target,
        "command": command,
    })
    return payload.get("prepared") or {}


def codebridge_discard(request_id=None):
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/terminal/discard"
    payload = _post_json(url, runtime["token"], {"request_id": request_id})
    return payload.get("result") or {}


def codebridge_execute_prepared(execution_request_id, prepared_request_id):
    runtime = _load_runtime()
    url = (
        f"http://{runtime['host']}:{int(runtime['port'])}"
        "/v1/terminal/execute-prepared"
    )
    payload = _post_json(
        url,
        runtime["token"],
        {
            "execution_request_id": execution_request_id,
            "prepared_request_id": prepared_request_id,
        },
        timeout=120.0,
    )
    return payload.get("execution") or {}


def codebridge_dispatch(request_id, target, command):
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/terminal/dispatch"
    payload = _post_json(
        url, runtime["token"],
        {"request_id": request_id, "target": target, "command": command},
        timeout=130.0,
    )
    return payload.get("dispatch") or {}


def codebridge_start_async(request_id, target, command):
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/executions/start"
    payload = _post_json(
        url, runtime["token"],
        {"request_id": request_id, "target": target, "command": command},
        timeout=8.0,
    )
    return payload.get("dispatch") or {}


def codebridge_execution_status(execution_id, cursor=0, max_chars=65536):
    runtime = _load_runtime()
    query = urlencode({"cursor": int(cursor or 0), "max_chars": int(max_chars or 65536)})
    safe_id = quote(str(execution_id), safe="")
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/executions/{safe_id}?{query}"
    payload = _get_json(url, runtime["token"], timeout=5.0)
    return payload.get("execution") or {}


def codebridge_v2_start(request_id, target, command):
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/phase5b/start"
    payload = _post_json(url, runtime["token"], {
        "request_id": request_id, "target": target, "command": command,
    }, timeout=8.0)
    return payload.get("execution") or {}


def codebridge_v2_status(execution_id):
    runtime = _load_runtime()
    safe_id = quote(str(execution_id), safe="")
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/phase5c/executions/{safe_id}"
    payload = _get_json(url, runtime["token"], timeout=5.0)
    return payload.get("execution") or {}

def codebridge_v2_result(execution_id):
    runtime = _load_runtime()
    safe_id = quote(str(execution_id), safe="")
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/phase5c/executions/{safe_id}/result"
    payload = _get_json(url, runtime["token"], timeout=5.0)
    return payload.get("result") or {}


def codebridge_v2_output(execution_id, cursor=0, max_chars=32768):
    runtime = _load_runtime()
    safe_id = quote(str(execution_id), safe="")
    query = urlencode({"cursor": int(cursor or 0), "max_chars": int(max_chars or 32768)})
    url = (
        f"http://{runtime['host']}:{int(runtime['port'])}"
        f"/v1/phase5f/executions/{safe_id}/output?{query}"
    )
    payload = _get_json(url, runtime["token"], timeout=8.0)
    return payload.get("output") or {}


def codebridge_v2_wait(
    execution_id,
    cursor=0,
    max_chars=32768,
    timeout_ms=15000,
):
    runtime = _load_runtime()
    safe_id = quote(str(execution_id), safe="")
    timeout_ms = max(
        0,
        min(int(timeout_ms or 0), 120000),
    )
    query = urlencode({
        "cursor": int(cursor or 0),
        "max_chars": int(max_chars or 32768),
        "timeout_ms": timeout_ms,
    })
    url = (
        f"http://{runtime['host']}:{int(runtime['port'])}"
        f"/v1/phase5f/executions/{safe_id}/wait?{query}"
    )
    payload = _get_json(
        url,
        runtime["token"],
        timeout=max(5.0, (timeout_ms / 1000.0) + 5.0),
    )
    return payload.get("output") or {}


def codebridge_v2_stop(execution_id):
    runtime = _load_runtime()
    safe_id = quote(str(execution_id), safe="")
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/phase5d/executions/{safe_id}/stop"
    payload = _post_json(url, runtime["token"], {}, timeout=5.0)
    return payload.get("stop") or {}

def codebridge_stop():
    runtime = _load_runtime()
    url = f"http://{runtime['host']}:{int(runtime['port'])}/v1/stop"
    payload = _post_json(url, runtime["token"], {})
    return {"cancelled": bool(payload.get("cancelled"))}
