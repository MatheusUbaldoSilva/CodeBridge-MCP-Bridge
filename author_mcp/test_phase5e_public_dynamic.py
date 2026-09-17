import asyncio
import json
import time
from pathlib import Path
from mcp.client.client import Client

ROOT = Path(__file__).resolve().parent
state = json.loads((ROOT / "stack_state.json").read_text(encoding="utf-8-sig"))
URL = state["mcp_url"]

async def content(result):
    value = getattr(result, "structuredContent", None)
    if value is None:
        value = getattr(result, "structured_content", None)
    if value is None:
        raise RuntimeError("sem structuredContent")
    return value

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools.tools]
        print("PUBLIC_URL", URL)
        print("V2_TOOLS", [x for x in names if x.startswith("codebridge_v2_")])
        t0 = time.perf_counter()
        start = await content(await client.call_tool("codebridge_v2_start", {
            "target": "POWERSHELL5.1",
            "command": "Write-Output 'P5E_PUBLIC_START'; Start-Sleep -Seconds 2; Write-Output 'P5E_PUBLIC_END'",
        }))
        print("START_MS", round((time.perf_counter()-t0)*1000), "HANDSHAKE", start.get("handshake_confirmed"))
        execution = start["execution"]
        eid = execution["execution_id"]
        print("EXECUTION_ID", eid, "STATE", execution.get("state"))
        for _ in range(20):
            await asyncio.sleep(0.35)
            status = await content(await client.call_tool("codebridge_v2_status", {"execution_id": eid}))
            state_now = status["execution"].get("state")
            print("STATE", state_now)
            if state_now in {"FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"}:
                break
        result = await content(await client.call_tool("codebridge_v2_result", {"execution_id": eid}))
        print("RESULT", json.dumps(result, ensure_ascii=False))
        out = result["execution"].get("output", "")
        ok = "P5E_PUBLIC_START" in out and "P5E_PUBLIC_END" in out
        print("PHASE5E_PUBLIC=" + ("PASS" if ok else "FAIL"))

asyncio.run(main())
