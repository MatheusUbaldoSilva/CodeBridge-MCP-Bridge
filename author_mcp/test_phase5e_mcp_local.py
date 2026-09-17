import asyncio
import json
import time
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def call(client, name, args):
    result = await client.call_tool(name, args)
    data = getattr(result, "structuredContent", getattr(result, "structured_content", None))
    if data is None:
        raise RuntimeError(f"sem structuredContent em {name}")
    return data

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools.tools]
        needed = ["codebridge_v2_start", "codebridge_v2_status", "codebridge_v2_result", "codebridge_v2_stop"]
        print("TOOLS_OK", all(n in names for n in needed), needed)

        started = time.perf_counter()
        first = await call(client, "codebridge_v2_start", {
            "target": "POWERSHELL5.1",
            "command": "Write-Output 'P5E_START'; Start-Sleep -Seconds 4; Write-Output 'P5E_END'",
        })
        elapsed = round((time.perf_counter() - started) * 1000)
        execution_id = first["execution"]["execution_id"]
        print("START_MS", elapsed, "ID", execution_id, "STATE", first["execution"]["state"], "HS", first["handshake_confirmed"])

        await asyncio.sleep(1.0)
        status1 = await call(client, "codebridge_v2_status", {"execution_id": execution_id})
        print("STATUS1", status1["execution"]["state"], "HS", status1["handshake_confirmed"])

        early = await call(client, "codebridge_v2_result", {"execution_id": execution_id})
        print("RESULT_EARLY", early["execution"].get("state"), early["execution"].get("ready"))

        deadline = time.monotonic() + 10
        final_status = None
        while time.monotonic() < deadline:
            final_status = await call(client, "codebridge_v2_status", {"execution_id": execution_id})
            if final_status["execution"].get("complete"):
                break
            await asyncio.sleep(0.35)
        final = await call(client, "codebridge_v2_result", {"execution_id": execution_id})
        print("FINAL", final["execution"]["state"], final["execution"]["exit_code"], repr(final["execution"]["output"]))

        second = await call(client, "codebridge_v2_start", {
            "target": "POWERSHELL5.1",
            "command": "Write-Output 'P5E_CANCEL_START'; Start-Sleep -Seconds 20; Write-Output 'P5E_CANCEL_END'",
        })
        cancel_id = second["execution"]["execution_id"]
        await asyncio.sleep(1.0)
        stop = await call(client, "codebridge_v2_stop", {"execution_id": cancel_id})
        print("STOP", stop["stop"].get("cancelled"), stop["stop"].get("reason"), "HS", stop["handshake_confirmed"])

        deadline = time.monotonic() + 8
        cancel_final = None
        while time.monotonic() < deadline:
            cancel_final = await call(client, "codebridge_v2_result", {"execution_id": cancel_id})
            if cancel_final["execution"].get("ready"):
                break
            await asyncio.sleep(0.25)
        payload = cancel_final["execution"]
        print("CANCEL_FINAL", payload.get("state"), payload.get("error_type"), repr(payload.get("output")))

        ok = (
            elapsed < 2000
            and first["handshake_confirmed"]
            and final["execution"]["state"] == "FINISHED"
            and "P5E_START" in final["execution"]["output"]
            and "P5E_END" in final["execution"]["output"]
            and stop["stop"].get("cancelled") is True
            and payload.get("state") == "CANCELLED"
            and "P5E_CANCEL_END" not in (payload.get("output") or "")
        )
        print("PHASE5E_MCP_LOCAL", "PASS" if ok else "FAIL")
        if not ok:
            raise SystemExit(2)

asyncio.run(main())
