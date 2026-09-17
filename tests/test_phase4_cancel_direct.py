import json
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

RUNTIME = Path(os.environ["LOCALAPPDATA"]) / "CodeBridge-MCP-Bridge" / "runtime.json"

def runtime():
    return json.loads(RUNTIME.read_text(encoding="utf-8"))

def request(method, path, payload=None, timeout=40):
    rt = runtime()
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"http://{rt['host']}:{rt['port']}{path}", data=body, method=method,
        headers={"Authorization": f"Bearer {rt['token']}", "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def wait_executing(target, timeout=5):
    key = {"POWERSHELL5.1": "powershell", "CMD": "cmd", "SSH": "ssh"}[target]
    end = time.time() + timeout
    while time.time() < end:
        status = request("GET", "/v1/status")["status"]["terminals"]
        if status[key]["executing"]:
            return status
        time.sleep(0.05)
    raise RuntimeError(f"{target} nao entrou em executing")
def run_case(index, target, command):
    box = {}
    rid = f"phase4_direct_cancel_{index}_{int(time.time() * 1000)}"
    def worker():
        try:
            box["result"] = request("POST", "/v1/terminal/dispatch", {
                "request_id": rid, "target": target, "command": command,
            })
        except Exception as exc:
            box["error"] = repr(exc)
    started = time.perf_counter()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    status = wait_executing(target)
    stop = request("POST", "/v1/stop", {})
    thread.join(timeout=6)
    elapsed = time.perf_counter() - started
    print(target, "STOP", stop, "ELAPSED", round(elapsed, 3), flush=True)
    print(target, "ALIVE", thread.is_alive(), flush=True)
    print(target, "RESULT", json.dumps(box, ensure_ascii=False), flush=True)
    return stop, box, elapsed, thread.is_alive()

def main():
    request("POST", "/v1/settings/auto", {"enabled": True})
    cases = [
        ("POWERSHELL5.1", "Write-Output 'DIRECT_PS_START'; Start-Sleep -Seconds 20; Write-Output 'DIRECT_PS_END'"),
        ("CMD", "echo DIRECT_CMD_START & ping -n 20 127.0.0.1 >nul & echo DIRECT_CMD_END"),
        ("SSH", "echo DIRECT_SSH_START; sleep 20; echo DIRECT_SSH_END"),
    ]
    failures = []
    for i, (target, command) in enumerate(cases, 1):
        stop, box, elapsed, alive = run_case(i, target, command)
        if not stop.get("cancelled"):
            failures.append(f"{target}: stop=false")
        if alive or elapsed > 8:
            failures.append(f"{target}: cancel demorou {elapsed:.2f}s")
        execution = ((box.get("result") or {}).get("dispatch") or {}).get("execution") or {}
        if execution.get("state") != "FAILED":
            failures.append(f"{target}: state={execution.get('state')}")
    request("POST", "/v1/settings/auto", {"enabled": False})
    if failures:
        raise SystemExit("FAIL: " + "; ".join(failures))
    print("PHASE4_DIRECT_CANCEL=OK", flush=True)

if __name__ == "__main__":
    main()
