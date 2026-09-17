import json
from pathlib import Path
import threading

from constants import CONFIG_FILE


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else CONFIG_FILE
        self._lock = threading.RLock()

    def _read(self):
        if not self.path.is_file():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config.json deve conter um objeto JSON")
        return data

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)

    def load_ssh(self):
        data = self._read()
        host = data.get("ssh_host")
        if not host:
            return None
        port = int(data.get("ssh_port", 22))
        return {"host": str(host).strip(), "port": port}

    def save_ssh(self, host, port=22):
        with self._lock:
            return self._save_ssh_locked(host, port)

    def _save_ssh_locked(self, host, port=22):
        host = str(host).strip()
        port = int(port)
        if not host:
            raise ValueError("ssh_host vazio")
        if port < 1 or port > 65535:
            raise ValueError("ssh_port invalida")
        data = self._read()
        data["ssh_host"] = host
        data["ssh_port"] = port
        self._write(data)
        return {"host": host, "port": port}


    def load_auto_execute(self):
        data = self._read()
        return bool(data.get("auto_execute", False))

    def save_auto_execute(self, enabled):
        with self._lock:
            data = self._read()
            data["auto_execute"] = bool(enabled)
            self._write(data)
            return bool(enabled)

    def clear_ssh(self):
        with self._lock:
            return self._clear_ssh_locked()

    def _clear_ssh_locked(self):
        data = self._read()
        removed = bool(data.pop("ssh_host", None) is not None)
        removed = bool(data.pop("ssh_port", None) is not None) or removed
        if data:
            self._write(data)
        elif self.path.exists():
            self.path.unlink()
        return removed
