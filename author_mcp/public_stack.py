import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from public_token import ensure_token, fingerprint

ROOT = Path(__file__).resolve().parent.parent
AUTHOR = ROOT / "author_mcp"
PORTABLE_PYTHON = ROOT / "runtime" / "python" / "python.exe"
VENV_PYTHON = AUTHOR / ".venv" / "Scripts" / "python.exe"
PYTHON = PORTABLE_PYTHON if PORTABLE_PYTHON.is_file() else VENV_PYTHON
NGROK = Path(r"C:\Users\Matheus\CodeBridge_MCP_Teste\ngrok\ngrok.exe")
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
STATE_FILE = DATA_DIR / "public_mcp_state.json"
PUBLIC_PORT = 8767


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def adapter_health():
    try:
        with urlopen("http://127.0.0.1:8766/health", timeout=1.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def wait_for(predicate, timeout=10.0, interval=0.15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


def read_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def command_line(pid):
    ps = (
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=%d\" -ErrorAction SilentlyContinue; "
        "if($p){$p.CommandLine}" % int(pid)
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, timeout=4,
    )
    return (result.stdout or "").strip()


def kill_owned(pid, marker):
    if not pid:
        return False
    line = command_line(pid)
    if not line or marker.lower() not in line.lower():
        return False
    subprocess.run(
        ["taskkill.exe", "/PID", str(int(pid)), "/T", "/F"],
        capture_output=True, text=True, timeout=8,
    )
    return True


def parse_ngrok_url(log_path):
    if not log_path.is_file():
        return None
    for raw in reversed(log_path.read_text(encoding="utf-8", errors="ignore").splitlines()):
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if row.get("msg") == "started tunnel" and row.get("url"):
            return str(row["url"])
    return None


def stop_stack():
    state = read_state()
    killed_mcp = kill_owned(state.get("mcp_pid"), "mcp_server.py")
    killed_ngrok = kill_owned(state.get("ngrok_pid"), "ngrok.exe")
    try:
        STATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return {
        "stopped": True,
        "mcp_stopped": killed_mcp,
        "ngrok_stopped": killed_ngrok,
        "public_port_open": port_open(PUBLIC_PORT),
    }


def require_local_stack():
    health = adapter_health()
    operations = set(health.get("operations") or [])
    needed = {"EXECUTION_V2_START", "EXECUTION_V2_STATUS", "EXECUTION_V2_RESULT", "EXECUTION_V2_OUTPUT", "EXECUTION_V2_STOP"}
    if not health.get("ok") or not needed.issubset(operations):
        raise RuntimeError("adapter local 8766 nao esta pronto")
    if not port_open(8765):
        raise RuntimeError("MCP local 8765 nao esta online")
    return health


def start_stack():
    require_local_stack()
    if port_open(PUBLIC_PORT):
        raise RuntimeError(f"porta publica local {PUBLIC_PORT} ja esta ocupada")
    if not NGROK.is_file():
        raise FileNotFoundError(f"ngrok nao encontrado: {NGROK}")
    if not PYTHON.is_file():
        raise FileNotFoundError(f"python autoral nao encontrado: {PYTHON}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    token = ensure_token()
    ngrok_log = DATA_DIR / "public_mcp_ngrok.log"
    mcp_log = DATA_DIR / "public_mcp_server.log"
    ngrok_log.write_text("", encoding="utf-8")

    ngrok = subprocess.Popen(
        [str(NGROK), "http", str(PUBLIC_PORT), "--log", str(ngrok_log), "--log-format", "json"],
        cwd=str(AUTHOR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    mcp = None
    try:
        public_url = None
        if not wait_for(lambda: bool(parse_ngrok_url(ngrok_log)), timeout=15.0):
            raise RuntimeError("ngrok nao publicou URL")
        public_url = parse_ngrok_url(ngrok_log)
        public_host = public_url.removeprefix("https://").removeprefix("http://").split("/", 1)[0]

        env = os.environ.copy()
        env["CODEBRIDGE_MCP_BEARER_TOKEN"] = token
        env["PYTHONUNBUFFERED"] = "1"
        with open(mcp_log, "a", encoding="utf-8", buffering=1) as handle:
            mcp = subprocess.Popen(
                [str(PYTHON), str(AUTHOR / "mcp_server.py"), "--host", "127.0.0.1",
                 "--port", str(PUBLIC_PORT), "--public-host", public_host, "--require-bearer"],
                cwd=str(AUTHOR), stdout=handle, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        if not wait_for(lambda: port_open(PUBLIC_PORT), timeout=10.0):
            raise RuntimeError("MCP publico local nao abriu porta 8767")
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "public_url": public_url,
            "mcp_url": public_url.rstrip("/") + "/mcp",
            "public_local_port": PUBLIC_PORT,
            "ngrok_pid": ngrok.pid,
            "mcp_pid": mcp.pid,
            "token_fingerprint": fingerprint(token),
            "auth": "static_bearer",
        }
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return state
    except Exception:
        if mcp is not None and mcp.poll() is None:
            subprocess.run(["taskkill.exe", "/PID", str(mcp.pid), "/T", "/F"], capture_output=True)
        if ngrok.poll() is None:
            subprocess.run(["taskkill.exe", "/PID", str(ngrok.pid), "/T", "/F"], capture_output=True)
        raise


def status_stack():
    state = read_state()
    return {
        **state,
        "public_port_open": port_open(PUBLIC_PORT),
        "local_adapter_online": bool(adapter_health().get("ok")),
        "local_mcp_online": port_open(8765),
    }


def main():
    command = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if command == "start":
        result = start_stack()
    elif command == "stop":
        result = stop_stack()
    elif command == "status":
        result = status_stack()
    else:
        raise SystemExit("use: start | stop | status")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
