import asyncio
import json
import time
from mcp.client.client import Client

URL = "https://d522-189-15-127-8.ngrok-free.app/mcp"

async def call(name, args):
    async with Client(URL) as client:
        result = await client.call_tool(name, args)
        return getattr(result, "structuredContent", getattr(result, "structured_content", None))

async def main():
    started = time.perf_counter()
    terminal = asyncio.create_task(call("codebridge_terminal", {
        "target": "POWERSHELL5.1",
        "command": "Write-Output 'PUBLIC_CANCEL_START'; Start-Sleep -Seconds 20; Write-Output 'PUBLIC_CANCEL_END'",
    }))
    await asyncio.sleep(1.5)
    stop = await call("codebridge_stop", {})
    result = await terminal
    print("ELAPSED", round(time.perf_counter() - started, 3))
    print("STOP", json.dumps(stop, ensure_ascii=False))
    print("TERMINAL", json.dumps(result, ensure_ascii=False))

asyncio.run(main())

