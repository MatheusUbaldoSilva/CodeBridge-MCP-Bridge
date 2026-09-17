import asyncio
import json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def call_tool(name, args):
    async with Client(URL) as client:
        result = await client.call_tool(name, args)
        data = getattr(result, "structuredContent", None)
        if data is None:
            data = getattr(result, "structured_content", None)
        return data

async def run_case(target, command):
    terminal_task = asyncio.create_task(
        call_tool("codebridge_terminal", {"target": target, "command": command})
    )
    await asyncio.sleep(1.5)
    stop_result = await call_tool("codebridge_stop", {})
    terminal_result = await terminal_task
    return stop_result, terminal_result

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print("TOOLS=", [t.name for t in tools.tools])
    cases = [
        ("POWERSHELL5.1", "Write-Output 'CANCEL_PS_START'; Start-Sleep -Seconds 20; Write-Output 'CANCEL_PS_END'"),
        ("CMD", "echo CANCEL_CMD_START & ping -n 20 127.0.0.1 >nul & echo CANCEL_CMD_END"),
        ("SSH", "echo CANCEL_SSH_START; sleep 20; echo CANCEL_SSH_END"),
    ]
    for target, command in cases:
        print("CASE", target)
        stop_result, terminal_result = await run_case(target, command)
        print("STOP=", json.dumps(stop_result, ensure_ascii=False))
        print("TERMINAL=", json.dumps(terminal_result, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
