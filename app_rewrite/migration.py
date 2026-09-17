import json
import os
from pathlib import Path

from config_store import ConfigStore
from credential_store import WindowsCredentialStore


def migrate_legacy_ssh_once():
    new_config = ConfigStore()
    new_credentials = WindowsCredentialStore()
    if new_config.load_ssh() is not None or new_credentials.exists():
        return False
    legacy_path = Path(os.environ.get("LOCALAPPDATA", "")) / "CodeBridge" / "config.json"
    if not legacy_path.is_file():
        return False
    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        host = str(data.get("ssh_host") or "").strip()
        port = int(data.get("ssh_port", 22))
        old_credentials = WindowsCredentialStore(target="CodeBridge:SSH").load()
        if not host or not old_credentials:
            return False
        new_config.save_ssh(host, port)
        new_credentials.save(old_credentials["username"], old_credentials["password"])
        return True
    except Exception:
        return False
