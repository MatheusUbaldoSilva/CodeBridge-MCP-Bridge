import json
import os
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
RUNTIME_FILE = DATA_DIR / "runtime.json"


class CodeBridgeUnavailable(RuntimeError):
    pass


def _load_runtime():
    if not RUNTIME_FILE.is_file():
        raise CodeBridgeUnavailable("runtime.json nao encontrado")
    data = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    for key in ("host", "port", "token"):
        if not data.get(key):
            raise CodeBridgeUnavailable(f"runtime.json sem {key}")
    return data


def _get_json(url, token, timeout=3.0):
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise CodeBridgeUnavailable(str(exc)) from exc


def _post_json(url, token, payload, timeout=5.0):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
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
        },
        "queue": status.get("queue"),
        "executor": status.get("executor"),
        "auto_execute": bool(status.get("auto_execute")),
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
