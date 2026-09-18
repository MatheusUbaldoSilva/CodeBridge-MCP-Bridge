import os
import subprocess
import time
from pathlib import Path

from author_mcp_status import AuthorMCPStatus


class AuthorMCPManager:
    ADAPTER_PORT = 8766
    MCP_PORT = 8765

    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent
        self.author_dir = self.root / "author_mcp"
        portable_python = self.root / "runtime" / "python" / "python.exe"
        venv_python = self.author_dir / ".venv" / "Scripts" / "python.exe"
        self.python = (
            portable_python if portable_python.is_file() else venv_python
        )
        local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        self.data_dir = local_appdata / "CodeBridge-MCP-Bridge"
        self.probe = AuthorMCPStatus()
        self._adapter_process = None
        self._mcp_process = None
        self._log_handles = []
        self._last_error = None
        self._managed = False

    @staticmethod
    def _process_running(process):
        return process is not None and process.poll() is None

    @staticmethod
    def _wait_for(predicate, timeout=6.0, interval=0.1):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def _open_log(self, filename):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        handle = open(
            self.data_dir / filename,
            "a",
            encoding="utf-8",
            buffering=1,
        )
        self._log_handles.append(handle)
        return handle

    def _spawn(self, script_name, args, log_name):
        if not self.python.is_file():
            raise FileNotFoundError(f"Python do MCP autoral nao encontrado: {self.python}")
        script = self.author_dir / script_name
        if not script.is_file():
            raise FileNotFoundError(f"Script do MCP autoral nao encontrado: {script}")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        log_handle = self._open_log(log_name)
        return subprocess.Popen(
            [str(self.python), str(script), *args],
            cwd=str(self.author_dir),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=creationflags,
        )

    def _terminate(self, process):
        if not self._process_running(process):
            return
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def start(self):
        current = self.probe.status()
        if current.get("state") == "ONLINE":
            self._last_error = None
            self._managed = False
            return self.status()
        if current.get("adapter_online") or current.get("mcp_online"):
            self._last_error = "stack MCP local parcialmente ocupada; inicio automatico bloqueado"
            return self.status()
        try:
            self._adapter_process = self._spawn(
                "adapter_server.py", [], "author_mcp_adapter.log"
            )
            if not self._wait_for(
                lambda: self.probe.status().get("adapter_online"), timeout=6.0
            ):
                raise RuntimeError("adapter MCP autoral nao ficou ONLINE")
            self._mcp_process = self._spawn(
                "mcp_server.py",
                ["--host", "127.0.0.1", "--port", str(self.MCP_PORT)],
                "author_mcp_server.log",
            )
            if not self._wait_for(
                lambda: self.probe.status().get("mcp_online"), timeout=8.0
            ):
                raise RuntimeError("servidor MCP autoral nao ficou ONLINE")
            self._managed = True
            self._last_error = None
            return self.status()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return self.status()

    def stop(self):
        self._terminate(self._mcp_process)
        self._terminate(self._adapter_process)
        self._mcp_process = None
        self._adapter_process = None
        self._managed = False
        while self._log_handles:
            handle = self._log_handles.pop()
            try:
                handle.close()
            except Exception:
                pass
        return self.status()

    def status(self):
        status = dict(self.probe.status())
        adapter_pid = (
            self._adapter_process.pid
            if self._process_running(self._adapter_process)
            else None
        )
        mcp_pid = (
            self._mcp_process.pid
            if self._process_running(self._mcp_process)
            else None
        )
        status.update({
            "managed_by_codebridge": bool(self._managed),
            "adapter_managed_pid": adapter_pid,
            "mcp_managed_pid": mcp_pid,
            "last_error": self._last_error,
        })
        return status
