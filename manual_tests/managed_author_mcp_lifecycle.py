import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
AUTHOR = ROOT / "author_mcp"
AUTHOR_PYTHON = AUTHOR / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(APP))

from runtime import BridgeRuntime


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


assert not port_open(8765), "porta 8765 ja estava ocupada antes do teste"
assert not port_open(8766), "porta 8766 ja estava ocupada antes do teste"
rt = BridgeRuntime()

client_code = r'''
import asyncio
from mcp.client.client import Client

async def main():
    async with Client("http://127.0.0.1:8765/mcp") as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        required = {"codebridge_status", "codebridge_v2_start", "codebridge_v2_output", "codebridge_v2_stop"}
        if not required.issubset(names):
            raise RuntimeError(f"tools ausentes: {sorted(required - names)}")
        result = await client.call_tool("codebridge_status", {})
        data = getattr(result, "structuredContent", None)
        if data is None:
            data = getattr(result, "structured_content", None)
        if not data or not data.get("handshake_confirmed") or data.get("overall") != "READY":
            raise RuntimeError(f"status MCP invalido: {data!r}")
        print("MCP_CLIENT_OK")

asyncio.run(main())
'''

try:
    rt.start()
    state = rt.snapshot()["author_mcp"]
    print("START_STATE", json.dumps(state, ensure_ascii=False))
    assert state.get("state") == "ONLINE", state
    assert state.get("managed_by_codebridge") is True, state
    assert state.get("adapter_managed_pid"), state
    assert state.get("mcp_managed_pid"), state

    child = subprocess.run(
        [str(AUTHOR_PYTHON), "-c", client_code],
        cwd=str(AUTHOR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(child.stdout, end="")
    if child.stderr:
        print(child.stderr, end="", file=sys.stderr)
    assert child.returncode == 0, child.returncode
    assert "MCP_CLIENT_OK" in child.stdout
finally:
    rt.stop()
    time.sleep(0.5)

print("PORT_8765_AFTER", port_open(8765))
print("PORT_8766_AFTER", port_open(8766))
assert not port_open(8765), "MCP 8765 permaneceu aberto apos runtime.stop"
assert not port_open(8766), "adapter 8766 permaneceu aberto apos runtime.stop"
print("MANAGED_AUTHOR_MCP_LIFECYCLE=PASS")
