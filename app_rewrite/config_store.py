import json
from pathlib import Path
import re
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
        temp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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

    @staticmethod
    def _profile_name_for(tunnel_id):
        suffix = re.sub(r"[^A-Za-z0-9_-]", "", str(tunnel_id))[-12:]
        return f"codebridge-{suffix or 'local'}"

    def load_company(self):
        data = self._read()
        tunnel_id = str(data.get("tunnel_id") or "").strip()
        profile_name = str(data.get("tunnel_profile_name") or "").strip()
        if tunnel_id and not profile_name:
            profile_name = self._profile_name_for(tunnel_id)
        return {
            "company_name": str(data.get("company_name") or "").strip(),
            "tunnel_id": tunnel_id,
            "profile_name": profile_name,
            "plugin_name": str(
                data.get("mcp_plugin_name") or "CodeBridge MCP"
            ).strip(),
        }

    def save_company(self, company_name, tunnel_id, plugin_name="CodeBridge MCP"):
        company_name = str(company_name or "").strip()
        tunnel_id = str(tunnel_id or "").strip()
        plugin_name = str(plugin_name or "").strip() or "CodeBridge MCP"
        if not tunnel_id.startswith("tunnel_"):
            raise ValueError("Tunnel ID invalido: esperado formato tunnel_...")
        if any(ch.isspace() for ch in tunnel_id):
            raise ValueError("Tunnel ID invalido: contem espacos")
        profile_name = self._profile_name_for(tunnel_id)
        with self._lock:
            data = self._read()
            data["company_name"] = company_name
            data["tunnel_id"] = tunnel_id
            data["tunnel_profile_name"] = profile_name
            data["mcp_plugin_name"] = plugin_name
            self._write(data)
        return {
            "company_name": company_name,
            "tunnel_id": tunnel_id,
            "profile_name": profile_name,
            "plugin_name": plugin_name,
        }

    def clear_company(self):
        with self._lock:
            data = self._read()
            removed = False
            for key in (
                "company_name", "tunnel_id",
                "tunnel_profile_name", "mcp_plugin_name",
            ):
                if data.pop(key, None) is not None:
                    removed = True
            if data:
                self._write(data)
            elif self.path.exists():
                self.path.unlink()
            return removed

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
