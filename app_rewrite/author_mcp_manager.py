import os
import subprocess
import time
from pathlib import Path

import psutil

from author_mcp_status import AuthorMCPStatus


class AuthorMCPManager:
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
        self._recycled_pids = []

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

    @staticmethod
    def _has_live_codebridge_ancestor(process):
        ancestor_pid = int(process.ppid() or 0)
        for _ in range(5):
            if ancestor_pid <= 0:
                break
            try:
                parent = psutil.Process(ancestor_pid)
                command = " ".join(
                    str(part)
                    for part in parent.cmdline()
                ).lower()
                if (
                    parent.is_running()
                    and "main.py" in command
                    and "codebridge" in command
                ):
                    return True
                ancestor_pid = int(parent.ppid() or 0)
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                OSError,
            ):
                break
        return False

    def _matching_stack_processes(self):
        author_dir = os.path.normcase(
            os.path.abspath(str(self.author_dir))
        )
        result = {
            "adapter": [],
            "mcp": [],
        }
        for process in psutil.process_iter(
            ["pid", "cmdline"]
        ):
            try:
                cmdline = [
                    str(part)
                    for part in (
                        process.info.get("cmdline") or []
                    )
                ]
                lowered = [
                    part.strip().lower()
                    for part in cmdline
                ]
                joined = os.path.normcase(
                    " ".join(cmdline)
                )
                if author_dir not in joined:
                    continue

                script_kind = None
                if any(
                    "adapter_server.py" in part
                    for part in lowered
                ):
                    script_kind = "adapter"
                elif any(
                    "mcp_server.py" in part
                    for part in lowered
                ):
                    port_matches = False
                    for index, part in enumerate(lowered):
                        if part != "--port":
                            continue
                        if index + 1 < len(lowered):
                            port_matches = (
                                lowered[index + 1]
                                == str(self.MCP_PORT)
                            )
                            break
                    if port_matches:
                        script_kind = "mcp"

                if not script_kind:
                    continue

                result[script_kind].append({
                    "pid": int(process.pid),
                    "live_codebridge_ancestor": (
                        self._has_live_codebridge_ancestor(
                            process
                        )
                    ),
                })
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                OSError,
                ValueError,
            ):
                continue
        return result

    @staticmethod
    def _terminate_pids(pids):
        processes = []
        for pid in sorted(
            {int(value) for value in pids},
            reverse=True,
        ):
            try:
                process = psutil.Process(pid)
                process.terminate()
                processes.append(process)
            except psutil.NoSuchProcess:
                continue

        if not processes:
            return

        gone, alive = psutil.wait_procs(
            processes,
            timeout=4.0,
        )
        del gone
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                continue
        if alive:
            psutil.wait_procs(alive, timeout=2.0)

    def _recycle_inherited_stack(self, current):
        processes = self._matching_stack_processes()
        adapter_online = bool(
            current.get("adapter_online")
        )
        mcp_online = bool(current.get("mcp_online"))

        if (
            adapter_online
            and not processes["adapter"]
        ):
            self._last_error = (
                "Adapter MCP local esta online, mas o processo "
                "nao pertence ao CodeBridge atual"
            )
            return False

        if mcp_online and not processes["mcp"]:
            self._last_error = (
                "Porta MCP local esta ocupada por processo "
                "nao reconhecido; recuperacao bloqueada"
            )
            return False

        candidates = (
            processes["mcp"]
            + processes["adapter"]
        )
        if any(
            item["live_codebridge_ancestor"]
            for item in candidates
        ):
            self._last_error = (
                "Stack MCP local pertence a outra instancia "
                "ativa do CodeBridge; recuperacao bloqueada"
            )
            return False

        pids = [
            item["pid"]
            for item in candidates
        ]
        try:
            self._terminate_pids(pids)
        except (
            psutil.AccessDenied,
            psutil.TimeoutExpired,
            OSError,
        ) as exc:
            self._last_error = (
                "Falha ao reciclar stack MCP herdada: "
                f"{type(exc).__name__}: {exc}"
            )
            return False

        if not self._wait_for(
            lambda: (
                self.probe.status().get("state")
                == "OFFLINE"
            ),
            timeout=6.0,
        ):
            self._last_error = (
                "Stack MCP herdada foi finalizada, mas "
                "as portas locais continuaram ocupadas"
            )
            return False

        self._recycled_pids = sorted(set(pids))
        return True

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
        if (
            current.get("adapter_online")
            or current.get("mcp_online")
        ):
            self._managed = False
            if not self._recycle_inherited_stack(current):
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
            "recycled_inherited_pids": list(
                self._recycled_pids
            ),
            "last_error": self._last_error,
        })
        return status
