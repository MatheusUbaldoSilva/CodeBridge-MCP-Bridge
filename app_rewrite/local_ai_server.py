"""IA Local: ciclo de vida do llama-server (Qwen2.5-Coder) controlado pelo CodeBridge.

O servidor roda como processo filho, so em 127.0.0.1, com chave aleatoria.
Modos: ON (fica carregado), OFF (libera a memoria), ON_DEMAND (carrega na
primeira mensagem e desliga sozinho apos IDLE_SECONDS sem uso).
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

AI_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CodeBridge" / "ai"
MODEL_NAME = "Qwen2.5-Coder 7B"
MODEL_FILE = AI_DIR / "models" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
SERVER_EXE = AI_DIR / "bin" / "llama-server.exe"
SETTINGS_FILE = AI_DIR / "settings.json"
LOG_FILE = AI_DIR / "logs" / "llama-server.log"
PID_FILE = AI_DIR / "llama-server.pid"

MODES = ("ON", "OFF", "ON_DEMAND")
DEFAULT_MODE = "ON_DEMAND"
IDLE_SECONDS = 600
CONTEXT_TOKENS = 8192
START_TIMEOUT_SECONDS = 180
# Pesos (4,4 GB) + cache de contexto 8k + buffers. Abaixo disso o modelo nao cabe.
REQUIRED_FREE_VRAM_MB = 5000
REQUIRED_FREE_RAM_MB = 800

STATE_OFF = "OFF"
STATE_LOADING = "LOADING"
STATE_READY = "READY"
STATE_ERROR = "ERROR"

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def load_mode(path: Path = SETTINGS_FILE) -> str:
    try:
        mode = json.loads(Path(path).read_text(encoding="utf-8")).get("mode")
    except (OSError, ValueError, AttributeError):
        return DEFAULT_MODE
    return mode if mode in MODES else DEFAULT_MODE


def save_mode(mode: str, path: Path = SETTINGS_FILE) -> None:
    if mode not in MODES:
        raise ValueError("modo invalido: " + str(mode))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": mode}) + "\n", encoding="utf-8")


def installed(model: Path = MODEL_FILE, exe: Path = SERVER_EXE) -> bool:
    return Path(model).is_file() and Path(exe).is_file()


def memory_snapshot() -> dict:
    """VRAM (nvidia-smi) e RAM (psutil) em MB; campos ausentes ficam None."""
    info = {"vram_total_mb": None, "vram_used_mb": None,
            "ram_total_mb": None, "ram_used_mb": None}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, creationflags=NO_WINDOW,
        )
        if out.returncode == 0 and out.stdout.strip():
            total, used = out.stdout.strip().splitlines()[0].split(",")[:2]
            info["vram_total_mb"] = int(float(total))
            info["vram_used_mb"] = int(float(used))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_mb"] = int(mem.total / 1048576)
        info["ram_used_mb"] = int((mem.total - mem.available) / 1048576)
    except Exception:
        pass
    return info


def start_blocker(memory: dict, *, model_loaded: bool = False) -> str | None:
    """Motivo em portugues para nao ligar, ou None se ha memoria suficiente."""
    if model_loaded:
        return None
    total, used = memory.get("vram_total_mb"), memory.get("vram_used_mb")
    if total is not None and used is not None:
        free = total - used
        if free < REQUIRED_FREE_VRAM_MB:
            return ("Memória insuficiente na placa de vídeo: livre %s, precisa %s. "
                    "Feche programas que usam a placa." % (_gb(free), _gb(REQUIRED_FREE_VRAM_MB)))
    total, used = memory.get("ram_total_mb"), memory.get("ram_used_mb")
    if total is not None and used is not None:
        free = total - used
        if free < REQUIRED_FREE_RAM_MB:
            return ("Memória insuficiente: livre %s de RAM, precisa %s. "
                    "Feche programas ou pause o RAG." % (_gb(free), _gb(REQUIRED_FREE_RAM_MB)))
    return None


def _gb(mb) -> str:
    return ("%.1f GB" % (mb / 1024)).replace(".", ",")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_command(exe: Path, model: Path, port: int, api_key: str) -> list[str]:
    return [
        str(exe), "-m", str(model),
        "--host", "127.0.0.1", "--port", str(port),
        "--api-key", api_key,
        "-ngl", "99", "-c", str(CONTEXT_TOKENS), "--parallel", "1",
        "--jinja",
    ]


class LocalAiServer:
    """Liga, desliga e vigia o llama-server. Seguro para chamar de varias threads."""

    def __init__(self, *, exe: Path = SERVER_EXE, model: Path = MODEL_FILE,
                 settings: Path = SETTINGS_FILE, popen=subprocess.Popen,
                 health=None, clock=time.monotonic, memory=memory_snapshot):
        self.exe, self.model, self.settings = Path(exe), Path(model), Path(settings)
        self._popen, self._clock, self._memory = popen, clock, memory
        self._health = health or self._http_health
        self._lock = threading.RLock()
        self._proc = None
        self._log = None
        self.state = STATE_OFF
        self.error = ""
        self.port = 0
        self.api_key = ""
        self.mode = load_mode(self.settings)
        self.busy = False
        self._last_used = clock()
        self._generation = 0

    # ---- informacao -------------------------------------------------------
    @property
    def base_url(self) -> str:
        return "http://127.0.0.1:%d" % self.port

    def is_installed(self) -> bool:
        return installed(self.model, self.exe)

    def is_running(self) -> bool:
        return self.state in (STATE_LOADING, STATE_READY)

    def idle_seconds_left(self) -> int | None:
        if self.mode != "ON_DEMAND" or self.state != STATE_READY or self.busy:
            return None
        return max(0, int(IDLE_SECONDS - (self._clock() - self._last_used)))

    # ---- controle ---------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError("modo invalido: " + str(mode))
        with self._lock:
            self.mode = mode
            save_mode(mode, self.settings)
            self.touch()
            if mode == "OFF":
                self.stop()
            elif mode == "ON":
                self.start()

    def touch(self) -> None:
        self._last_used = self._clock()

    def start(self) -> bool:
        """Inicia o carregamento em segundo plano. False se nao pode ligar."""
        with self._lock:
            if self.is_running():
                return True
            if not self.is_installed():
                self.state, self.error = STATE_ERROR, "Modelo não instalado em " + str(AI_DIR)
                return False
            blocker = start_blocker(self._memory())
            if blocker:
                self.state, self.error = STATE_ERROR, blocker
                return False
            self._kill_stale()
            self.port = _free_port()
            self.api_key = secrets.token_hex(16)
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(LOG_FILE, "ab")
            try:
                self._proc = self._popen(
                    build_command(self.exe, self.model, self.port, self.api_key),
                    stdout=self._log, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                    cwd=str(self.exe.parent),
                )
            except OSError as exc:
                self._close_log()
                self.state, self.error = STATE_ERROR, "Não foi possível iniciar: " + str(exc)
                return False
            self._write_pid()
            self.state, self.error = STATE_LOADING, ""
            self._generation += 1
            self.touch()
            threading.Thread(target=self._wait_ready, args=(self._generation,),
                             name="LocalAiWaitReady", daemon=True).start()
            return True

    def stop(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
            self._generation += 1
            self.state, self.busy = STATE_OFF, False
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._close_log()
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    def tick(self) -> None:
        """Chamado periodicamente: detecta queda do processo e desliga por inatividade."""
        with self._lock:
            proc = self._proc
            if proc is not None and proc.poll() is not None and self.is_running():
                self._proc = None
                self._close_log()
                self.state = STATE_ERROR
                self.error = "O servidor da IA fechou (código %s). Veja %s" % (proc.returncode, LOG_FILE)
                return
            left = self.idle_seconds_left()
        if left == 0:
            self.stop()

    def wait_ready(self, timeout: float = START_TIMEOUT_SECONDS, cancelled=None) -> bool:
        end = self._clock() + timeout
        while self._clock() < end:
            if self.state == STATE_READY:
                return True
            if self.state in (STATE_OFF, STATE_ERROR):
                return False
            if cancelled is not None and cancelled():
                return False
            time.sleep(0.25)
        return self.state == STATE_READY

    # ---- interno ----------------------------------------------------------
    def _wait_ready(self, generation: int) -> None:
        end = time.monotonic() + START_TIMEOUT_SECONDS
        while time.monotonic() < end:
            with self._lock:
                if generation != self._generation:
                    return
                proc = self._proc
            if proc is None or proc.poll() is not None:
                with self._lock:
                    if generation == self._generation:
                        self.state = STATE_ERROR
                        self.error = "O servidor da IA fechou ao carregar. Veja " + str(LOG_FILE)
                return
            if self._health(self.port, self.api_key):
                with self._lock:
                    if generation == self._generation:
                        self.state = STATE_READY
                        self.touch()
                return
            time.sleep(0.5)
        with self._lock:
            if generation == self._generation:
                self.error = "A IA demorou demais para carregar."
        self.stop()
        self.state = STATE_ERROR

    @staticmethod
    def _http_health(port: int, api_key: str) -> bool:
        request = urllib.request.Request(
            "http://127.0.0.1:%d/health" % port,
            headers={"Authorization": "Bearer " + api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _close_log(self) -> None:
        log, self._log = self._log, None
        if log is not None:
            try:
                log.close()
            except OSError:
                pass

    def _write_pid(self) -> None:
        try:
            PID_FILE.write_text(str(self._proc.pid), encoding="utf-8")
        except (OSError, AttributeError):
            pass

    @staticmethod
    def _kill_stale() -> None:
        """Encerra um llama-server que sobrou de uma sessao que caiu."""
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        try:
            import psutil
            proc = psutil.Process(pid)
            if proc.name().lower().startswith("llama-server"):
                proc.kill()
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except OSError:
            pass
