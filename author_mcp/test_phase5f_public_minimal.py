import asyncio
import json
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
    command = "1..2000 | ForEach-Object { Write-Output ('P5F_PUB_{0:D4}_{1}' -f $_, ('Y'*26)); if(($_ % 100) -eq 0){ Start-Sleep -Milliseconds 50 } }"
    async with Client(URL) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools.tools]
        assert "codebridge_v2_output" in names
        start = await content(await client.call_tool("codebridge_v2_start", {
            "target": "POWERSHELL5.1", "command": command,
        }))
        eid = start["execution"]["execution_id"]
        print("PUBLIC_URL", URL)
        print("START", start.get("handshake_confirmed"), eid, start["execution"].get("state"))
        cursor = 0
        pieces = []
        saw_running = False
        for index in range(80):
            await asyncio.sleep(0.12)
            chunk = await content(await client.call_tool("codebridge_v2_output", {
                "execution_id": eid, "cursor": cursor, "max_chars": 4096,
            }))
            out = chunk["output"]
            if out.get("text"):
                pieces.append(out["text"])
            cursor = int(out.get("next_cursor", cursor))
            status = await content(await client.call_tool("codebridge_v2_status", {
                "execution_id": eid,
            }))
            state_now = status["execution"].get("state")
            saw_running = saw_running or state_now == "RUNNING"
            if index < 4:
                print("READ", index + 1, state_now, out.get("chars"), cursor, out.get("has_more"), out.get("eof"))
            if status["execution"].get("complete") and not out.get("has_more"):
                break

        text = "".join(pieces)
        print("FINAL", state_now, "READS", index + 1, "CURSOR", cursor, "LEN", len(text), "SAW_RUNNING", saw_running)
        ok = (
            start.get("handshake_confirmed") is True
            and state_now == "FINISHED"
            and saw_running
            and 70000 <= len(text) <= 100000
            and "P5F_PUB_0001_" in text
            and "P5F_PUB_2000_" in text
        )
        print("PHASE5F_PUBLIC_MINIMAL=" + ("PASS" if ok else "FAIL"))
        if not ok:
            raise SystemExit(2)

asyncio.run(main())
