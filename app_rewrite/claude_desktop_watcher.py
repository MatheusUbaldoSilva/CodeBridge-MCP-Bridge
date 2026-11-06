"""Vigia do app desktop do Claude para o cronometro de turno.

Roda claude_desktop_watcher.ps1 (UI Automation do Windows) em segundo
plano e chama on_response_finished quando o botao "Interromper resposta"
aparece e depois some, assim como a extensao do navegador faz no ChatGPT.
"""

import os
import subprocess
import threading
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().with_name(
    "claude_desktop_watcher.ps1"
)


class ClaudeDesktopWatcher:
    def __init__(
        self,
        on_response_finished,
        script_path=SCRIPT_PATH,
        popen=None,
    ):
        self._on_finished = on_response_finished
        self._script = Path(script_path)
        self._popen = popen or subprocess.Popen
        self._lock = threading.RLock()
        self._proc = None
        self._thread = None
        self._state = "OFF"
        self._error = None
        self._finish_count = 0
        self._stopping = False

    def status(self):
        with self._lock:
            proc = self._proc
            running = bool(
                proc is not None
                and proc.poll() is None
            )
            return {
                "running": running,
                "state": self._state if running else "OFF",
                "error": self._error,
                "finished_responses": self._finish_count,
            }

    def start(self):
        with self._lock:
            if (
                self._proc is not None
                and self._proc.poll() is None
            ):
                return False
            if os.name != "nt":
                self._error = "vigia disponivel apenas no Windows"
                return False
            if not self._script.is_file():
                self._error = "script do vigia ausente: " + str(self._script)
                return False

            command = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self._script),
                "-ParentPid",
                str(os.getpid()),
            ]
            try:
                proc = self._popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=getattr(
                        subprocess,
                        "CREATE_NO_WINDOW",
                        0,
                    ),
                )
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                return False

            self._proc = proc
            self._state = "STARTING"
            self._error = None
            self._stopping = False
            self._thread = threading.Thread(
                target=self._reader,
                args=(proc,),
                name="CodeBridgeClaudeDesktopWatcher",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self):
        with self._lock:
            proc = self._proc
            self._proc = None
            self._stopping = True
            self._state = "OFF"

        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        return True

    def _reader(self, proc):
        try:
            self.consume(proc.stdout)
        except Exception as exc:
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                if self._proc is proc and not self._stopping:
                    self._error = self._error or "vigia encerrou"

    def consume(self, lines):
        previous = None
        for raw in lines:
            state = str(raw or "").strip().upper()
            if not state:
                continue
            with self._lock:
                self._state = state
            if previous == "RUNNING" and state != "RUNNING":
                with self._lock:
                    self._finish_count += 1
                try:
                    self._on_finished()
                except Exception:
                    pass
            previous = state
