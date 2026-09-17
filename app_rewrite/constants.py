import os
from pathlib import Path

APP_NAME = "CodeBridge 2.0 - MCP Bridge"
APP_VERSION = "2.0.0-prealpha"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
CONFIG_FILE = DATA_DIR / "config.json"
JOBS_DB = DATA_DIR / "jobs.db"
RUNTIME_FILE = DATA_DIR / "runtime.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_POLL_INTERVAL = 0.10
VALID_TARGETS = ("POWERSHELL5.1", "CMD", "SSH")
TERMINAL_ALIASES = {
    "POWERSHELL": "POWERSHELL5.1", "PS": "POWERSHELL5.1", "WINDOWS": "POWERSHELL5.1",
    "POWERSHELL5.1": "POWERSHELL5.1", "CMD": "CMD", "SSH": "SSH", "LINUX": "SSH",
}
