import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT_DIR / "version.json"


def _load_app_version():
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        return str(data.get("version") or "2.0.1-prealpha")
    except Exception:
        return "2.0.1-prealpha"


APP_NAME = "CodeBridge 2.0 - MCP Bridge"
APP_VERSION = _load_app_version()
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
CONFIG_FILE = DATA_DIR / "config.json"
JOBS_DB = DATA_DIR / "jobs.db"
RUNTIME_FILE = DATA_DIR / "runtime.json"
DEFAULT_HOST = "127.0.0.1"
VALID_TARGETS = ("POWERSHELL5.1", "CMD", "SSH")
TERMINAL_ALIASES = {
    "POWERSHELL": "POWERSHELL5.1", "PS": "POWERSHELL5.1", "WINDOWS": "POWERSHELL5.1",
    "POWERSHELL5.1": "POWERSHELL5.1", "CMD": "CMD", "SSH": "SSH", "LINUX": "SSH",
}
