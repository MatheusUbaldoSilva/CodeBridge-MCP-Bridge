import asyncio
import json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print("TOOLS=", [t.name for t in tools.tools])
        prep = await client.call_tool(
            "codebridge_prepare",
            {"target": "POWERSHELL5.1", "command": "Write-Output 'PHASE4_ENTER_CONTROLLED_PS'"},
        )
        pdata = getattr(prep, "structuredContent", None)
        if pdata is None:
            pdata = getattr(prep, "structured_content", None)
        print("PREPARE=", json.dumps(pdata, ensure_ascii=False, indent=2))
        execute = await client.call_tool(
            "codebridge_execute_prepared",
            {"prepared_request_id": pdata["request_id"]},
        )
        edata = getattr(execute, "structuredContent", None)
        if edata is None:
            edata = getattr(execute, "structured_content", None)
        print("EXECUTE=", json.dumps(edata, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
