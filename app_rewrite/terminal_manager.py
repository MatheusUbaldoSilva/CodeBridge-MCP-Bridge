import codecs
import re
import threading

from cmd_terminal_session import CmdTerminalSession
from config_store import ConfigStore
from credential_store import WindowsCredentialStore
from linux_terminal_session import LinuxTerminalSession
from windows_terminal_session import WindowsTerminalSession
from constants import TERMINAL_ALIASES


_ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")


class TerminalManager:
    def __init__(self, config_store=None, credential_store=None):
        self.config = config_store or ConfigStore()
        self.credentials = credential_store or WindowsCredentialStore()
        self._lock = threading.RLock()
        self.windows = WindowsTerminalSession()
        self.cmd = CmdTerminalSession()
        self.ssh = None
        self.ssh_last_error = None
        self.active_target = None
        self._prepared_target = None
        self._logs = {"POWERSHELL5.1": "", "CMD": "", "SSH": ""}
        self._log_generation = {"POWERSHELL5.1": 0, "CMD": 0, "SSH": 0}
        self._log_limit = 120000
        self._raw_streams = {"POWERSHELL5.1": "", "CMD": "", "SSH": ""}
        self._raw_generation = {"POWERSHELL5.1": 0, "CMD": 0, "SSH": 0}
        self._raw_base = {"POWERSHELL5.1": 0, "CMD": 0, "SSH": 0}
        self._raw_limit = 5000000
        self._raw_decoders = {
            key: codecs.getincrementaldecoder("utf-8")(errors="replace")
            for key in self._raw_streams
        }

    @staticmethod
    def normalize_target(target):
        key = str(target).strip().upper()
        try:
            return TERMINAL_ALIASES[key]
        except KeyError as exc:
            raise ValueError(f"target invalido: {target}") from exc
    @staticmethod
    def _clean_text(data):
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = str(data)
        text = _ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
        return text

    def _append_log(self, target, data):
        text = self._clean_text(data)
        if not text:
            return
        with self._lock:
            value = self._logs[target] + text
            if len(value) > self._log_limit:
                value = value[-self._log_limit:]
                self._log_generation[target] += 1
            self._logs[target] = value

    def log_snapshot(self, target):
        target = self.normalize_target(target)
        with self._lock:
            return self._logs[target]

    def log_delta(self, target, generation, position):
        target = self.normalize_target(target)
        with self._lock:
            current_generation = self._log_generation[target]
            value = self._logs[target]
            if generation != current_generation or position > len(value):
                return current_generation, len(value), value, True
            return current_generation, len(value), value[position:], False

    def clear_log(self, target):
        target = self.normalize_target(target)
        with self._lock:
            self._logs[target] = ""
            self._log_generation[target] += 1

    def announce(self, target, message):
        target = self.normalize_target(target)
        self._append_log(target, "\n" + str(message).rstrip() + "\n")

    def _append_raw(self, target, data):
        target = self.normalize_target(target)
        with self._lock:
            if isinstance(data, bytes):
                text = self._raw_decoders[target].decode(data, final=False)
            else:
                text = str(data)
            if not text:
                return
            value = self._raw_streams[target] + text
            if len(value) > self._raw_limit:
                drop = len(value) - self._raw_limit
                value = value[drop:]
                self._raw_base[target] += drop
            self._raw_streams[target] = value

    def raw_delta(self, target, generation, position):
        target = self.normalize_target(target)
        with self._lock:
            current = self._raw_generation[target]
            value = self._raw_streams[target]
            base = self._raw_base[target]
            end = base + len(value)
            if generation != current or position < base or position > end:
                return current, end, value, True
            return current, end, value[position - base:], False

    def _reset_raw(self, target):
        target = self.normalize_target(target)
        with self._lock:
            self._raw_streams[target] = ""
            self._raw_generation[target] += 1
            self._raw_base[target] = 0
            self._raw_decoders[target] = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def _callback(self, target):
        def callback(data):
            self._append_raw(target, data)
            self._append_log(target, data)
        return callback
    def start(self):
        self.windows.start(on_output=self._callback("POWERSHELL5.1"), width=120, height=40)
        self.cmd.start(on_output=self._callback("CMD"), width=120, height=40)
        ssh_config = self.config.load_ssh()
        if ssh_config and self.credentials.exists():
            try:
                self._connect_saved_ssh(ssh_config)
            except Exception as exc:
                self.ssh_last_error = f"{type(exc).__name__}: {exc}"
        return self.status()

    def _new_ssh_session(self, host, port, username, password):
        return LinuxTerminalSession(
            host=host,
            username=username,
            password=password,
            port=int(port),
            connect_timeout=10,
        )

    def _connect_saved_ssh(self, ssh_config):
        credentials = self.credentials.load()
        if not credentials:
            return False
        session = self._new_ssh_session(
            ssh_config["host"], ssh_config["port"],
            credentials["username"], credentials["password"],
        )
        session.start(on_output=self._callback("SSH"), width=120, height=40)
        with self._lock:
            old = self.ssh
            self.ssh = session
            self.ssh_last_error = None
        if old is not None:
            old.close()
        return True
    def ssh_settings(self):
        config = self.config.load_ssh() or {}
        credentials = self.credentials.load() or {}
        with self._lock:
            ssh = self.ssh
        return {
            "host": config.get("host", ""),
            "port": int(config.get("port", 22)),
            "username": credentials.get("username", ""),
            "password_saved": bool(credentials),
            "online": bool(ssh is not None and ssh.is_running),
            "last_error": self.ssh_last_error,
        }

    def test_ssh(self, host, port, username, password):
        candidate = self._new_ssh_session(host, port, username, password)
        try:
            candidate.start(on_output=None, width=120, height=40)
            return bool(candidate.is_running)
        finally:
            candidate.close()

    def configure_ssh(self, host, port, username, password):
        host = str(host).strip()
        username = str(username).strip()
        if not host or not username:
            raise ValueError("host e login SSH sao obrigatorios")
        candidate = self._new_ssh_session(host, port, username, password)
        candidate.start(on_output=self._callback("SSH"), width=120, height=40)
        try:
            self.config.save_ssh(host, port)
            self.credentials.save(username, password)
        except Exception:
            candidate.close()
            raise
        with self._lock:
            old = self.ssh
            self.ssh = candidate
            self.ssh_last_error = None
        if old is not None:
            old.close()
        self.announce("SSH", f"[SSH] Conectado a {host}:{int(port)} como {username}")
        return self.ssh_settings()

    def send_input(self, target, data):
        target = self.normalize_target(target)
        session = self._ensure_session(target)
        session.send(data)
        return True

    def resize(self, target, cols, rows):
        target = self.normalize_target(target)
        cols = int(cols)
        rows = int(rows)
        # Abas WebEngine ocultas podem reportar tamanhos minimos durante o layout.
        # Aceitamos terminais estreitos reais, mas descartamos geometria claramente invalida.
        if cols < 20 or rows < 5:
            return False
        session = self._ensure_session(target)
        session.resize(min(cols, 400), min(rows, 200))
        return True

    def _ensure_session(self, target):
        if target == "POWERSHELL5.1":
            if not self.windows.is_running:
                self._reset_raw(target)
                self.windows.start(on_output=self._callback(target), width=120, height=40)
            return self.windows
        if target == "CMD":
            if not self.cmd.is_running:
                self._reset_raw(target)
                self.cmd.start(on_output=self._callback(target), width=120, height=40)
            return self.cmd
        with self._lock:
            ssh = self.ssh
        if ssh is None or not ssh.is_running:
            config = self.config.load_ssh()
            if not config or not self.credentials.exists():
                raise RuntimeError("SSH nao configurado")
            self._connect_saved_ssh(config)
            with self._lock:
                ssh = self.ssh
        return ssh

    def prepare(self, target, command):
        target = self.normalize_target(target)
        session = self._ensure_session(target)
        with self._lock:
            if self.active_target is not None or self._prepared_target is not None:
                raise RuntimeError("outro comando ja possui autoridade sobre os terminais")
            self.active_target = target
            self._prepared_target = target
        self.announce(target, f"[PREPARED] {target}\n> {command}")
        ok = session.prepare_command(command, character_delay=0.0)
        if not ok:
            self.discard_prepared()
            raise RuntimeError("nao foi possivel preparar o comando")
        return True
    def execute_prepared(self, target, command, on_output=None):
        target = self.normalize_target(target)
        session = self._ensure_session(target)
        with self._lock:
            if self._prepared_target != target:
                raise RuntimeError("comando nao esta preparado no terminal")
            self.active_target = target
        self.announce(target, "[RUNNING] Enter enviado")
        try:
            return session.execute(command, on_output=on_output, prepared=True)
        finally:
            with self._lock:
                self._prepared_target = None
                self.active_target = None

    def execute(self, target, command):
        target = self.normalize_target(target)
        session = self._ensure_session(target)
        with self._lock:
            self.active_target = target
        self.announce(target, f"[RUNNING] {target}\n> {command}")
        try:
            return session.execute(command, on_output=None, prepared=False)
        finally:
            with self._lock:
                self.active_target = None

    def discard_prepared(self):
        with self._lock:
            target = self._prepared_target
            self._prepared_target = None
            self.active_target = None
        if target is None:
            return False
        try:
            if target == "POWERSHELL5.1" and self.windows.is_running:
                self.windows.send(b"\x1b[21~")
            elif target == "CMD" and self.cmd.is_running:
                self.cmd.send(b"\x1b")
            elif target == "SSH" and self.ssh is not None and self.ssh.is_running:
                self.ssh.send(b"\x15")
        finally:
            self.announce(target, "[CANCELLED] comando preparado descartado")
        return True
    def cancel_active(self):
        with self._lock:
            target = self.active_target
            prepared = self._prepared_target
            ssh = self.ssh
        # execute_prepared mantem _prepared_target ate o fim da execucao.
        # Priorize Ctrl+C quando a sessao realmente estiver executando.
        if target == "POWERSHELL5.1" and self.windows.is_executing:
            return self.windows.cancel_current()
        if target == "CMD" and self.cmd.is_executing:
            return self.cmd.cancel_current()
        if target == "SSH" and ssh is not None and ssh.is_executing:
            return ssh.cancel_current()
        if prepared is not None:
            return self.discard_prepared()
        return False

    def status(self):
        with self._lock:
            ssh = self.ssh
            active = self.active_target
            prepared = self._prepared_target
        return {
            "powershell": {"online": bool(self.windows.is_running), "executing": bool(self.windows.is_executing)},
            "cmd": {"online": bool(self.cmd.is_running), "executing": bool(self.cmd.is_executing)},
            "ssh": {
                "configured": bool(self.config.load_ssh() and self.credentials.exists()),
                "online": bool(ssh is not None and ssh.is_running),
                "executing": bool(ssh is not None and ssh.is_executing),
                "last_error": self.ssh_last_error,
            },
            "active_target": active,
            "prepared_target": prepared,
        }

    def close(self):
        try:
            if self.windows.is_running:
                self.windows.close()
        finally:
            try:
                if self.cmd.is_running:
                    self.cmd.close()
            finally:
                with self._lock:
                    ssh = self.ssh
                    self.ssh = None
                if ssh is not None:
                    ssh.close()
