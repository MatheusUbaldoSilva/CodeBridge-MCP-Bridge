import asyncio, json, time
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def call(client, name, args):
    r = await client.call_tool(name, args)
    data = getattr(r, "structuredContent", getattr(r, "structured_content", None))
    if data is None:
        raise RuntimeError(f"sem structuredContent em {name}")
    return data

async def wait_terminal(client, execution_id, timeout=15):
    end = time.time() + timeout
    seen = []
    while time.time() < end:
        s = await call(client, "codebridge_v2_status", {"execution_id": execution_id})
        e = s.get("execution") or {}
        state = e.get("state")
        seen.append(state)
        if state in ("FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"):
            return s, seen
        await asyncio.sleep(0.25)
    raise TimeoutError(execution_id)
async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools.tools]
        needed = {"codebridge_v2_start","codebridge_v2_status","codebridge_v2_result","codebridge_v2_stop"}
        print("TOOLS_OK", needed.issubset(names), sorted(needed))

        t0 = time.perf_counter()
        start = await call(client, "codebridge_v2_start", {
            "target": "POWERSHELL5.1",
            "command": "Write-Output 'P5E_START'; Start-Sleep -Seconds 3; Write-Output 'P5E_END'",
        })
        dt = round((time.perf_counter()-t0)*1000)
        execution = start.get("execution") or {}
        eid = execution.get("execution_id")
        print("START_MS", dt, "HANDSHAKE", start.get("handshake_confirmed"), "STATE", execution.get("state"), "ID", eid)

        status, seen = await wait_terminal(client, eid)
        result = await call(client, "codebridge_v2_result", {"execution_id": eid})
        print("STATES", seen)
        print("FINAL", json.dumps(status, ensure_ascii=False))
        print("RESULT", json.dumps(result, ensure_ascii=False))

        t1 = time.perf_counter()
        longrun = await call(client, "codebridge_v2_start", {
            "target": "POWERSHELL5.1",
            "command": "Write-Output 'P5E_CANCEL_START'; Start-Sleep -Seconds 20; Write-Output 'P5E_CANCEL_END'",
        })
        eid2 = (longrun.get("execution") or {}).get("execution_id")
        await asyncio.sleep(1.0)
        stop = await call(client, "codebridge_v2_stop", {"execution_id": eid2})
        final2, seen2 = await wait_terminal(client, eid2)
        result2 = await call(client, "codebridge_v2_result", {"execution_id": eid2})
        print("STOP_MS", round((time.perf_counter()-t1)*1000), "STOP", json.dumps(stop, ensure_ascii=False))
        print("CANCEL_STATES", seen2)
        print("CANCEL_RESULT", json.dumps(result2, ensure_ascii=False))

asyncio.run(main())
