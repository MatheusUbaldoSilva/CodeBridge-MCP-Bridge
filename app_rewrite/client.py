import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from constants import RUNTIME_FILE
from job_store import TERMINAL_STATES


class BridgeClientError(RuntimeError):
    pass


class BridgeClient:
    def __init__(self):
        if not RUNTIME_FILE.is_file():
            raise BridgeClientError("CodeBridge 2.0 nao esta em execucao")
        runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        self.base_url = f"http://{runtime['host']}:{runtime['port']}"
        self.token = runtime["token"]

    def _request(self, method, path, payload=None, timeout=5):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BridgeClientError(body or str(exc)) from exc
        except URLError as exc:
            raise BridgeClientError(f"CodeBridge 2.0 indisponivel: {exc}") from exc
        if not result.get("ok"):
            raise BridgeClientError(result.get("message") or result.get("error") or "erro desconhecido")
        return result

    def status(self):
        return self._request("GET", "/v1/status")["status"]

    def submit(self, target, command):
        return self._request("POST", "/v1/jobs", {"target": target, "command": command})["job"]

    def approve(self, job_id):
        return self._request("POST", f"/v1/jobs/{job_id}/approve", {})["job"]

    def get_job(self, job_id):
        return self._request("GET", f"/v1/jobs/{job_id}")["job"]

    def cancel(self, job_id):
        return bool(self._request("POST", f"/v1/jobs/{job_id}/cancel", {})["cancelled"])

    def stop(self):
        return bool(self._request("POST", "/v1/stop", {})["cancelled"])

    def ssh_settings(self):
        return self._request("GET", "/v1/ssh/config")["ssh"]

    def test_ssh(self, host, port, username, password):
        return self._request(
            "POST", "/v1/ssh/test",
            {"host": host, "port": int(port), "username": username, "password": password},
            timeout=15,
        )["ssh"]
    def configure_ssh(self, host, port, username, password):
        return self._request(
            "POST", "/v1/ssh/config",
            {"host": host, "port": int(port), "username": username, "password": password},
            timeout=15,
        )["ssh"]

    def wait(self, job_id, timeout=60, poll_interval=0.05):
        deadline = time.monotonic() + float(timeout)
        while True:
            job = self.get_job(job_id)
            if job["state"] in TERMINAL_STATES:
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timeout aguardando job {job_id}")
            time.sleep(poll_interval)

    def wait_field(self, job_id, field, timeout=2.0, poll_interval=0.05):
        deadline = time.monotonic() + float(timeout)
        while True:
            job = self.get_job(job_id)
            if job.get(field):
                return True
            if job["state"] in TERMINAL_STATES:
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval)

    def run(self, target, command, timeout=60):
        started = time.perf_counter()
        job = self.submit(target, command)
        self.wait_field(job["id"], "visible_at", timeout=2.0)
        self.approve(job["id"])
        result = self.wait(job["id"], timeout=timeout)
        result["round_trip_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
        return result
