import json
import socket
from pathlib import Path
from urllib.request import urlopen


class AuthorMCPStatus:
    def __init__(self):
        root = Path(__file__).resolve().parent.parent
        self.state_file = root / "author_mcp" / "stack_state.json"

    @staticmethod
    def _port_open(port):
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.25):
                return True
        except OSError:
            return False

    def status(self):
        saved = {}
        try:
            if self.state_file.is_file():
                saved = json.loads(self.state_file.read_text(encoding="utf-8-sig"))
        except Exception:
            saved = {}
        health = {}
        try:
            with urlopen("http://127.0.0.1:8766/health", timeout=0.5) as response:
                health = json.loads(response.read().decode("utf-8"))
        except Exception:
            health = {}
        operations = set(health.get("operations") or [])
        required = {"EXECUTION_V2_START", "EXECUTION_V2_STATUS", "EXECUTION_V2_RESULT", "EXECUTION_V2_STOP", "EXECUTION_V2_OUTPUT"}
        adapter_ok = bool(health.get("ok") and required.issubset(operations))
        mcp_ok = self._port_open(8765)
        if adapter_ok and mcp_ok:
            state = "ONLINE"
        elif adapter_ok or mcp_ok:
            state = "DEGRADED"
        else:
            state = "OFFLINE"
        return {
            "state": state,
            "adapter_online": adapter_ok,
            "mcp_online": mcp_ok,
            "adapter_pid": health.get("pid"),
            "public_url": saved.get("public_url"),
            "mcp_url": saved.get("mcp_url"),
            "operations": sorted(operations),
        }
