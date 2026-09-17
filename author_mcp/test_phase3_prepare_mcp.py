import asyncio
import json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print("TOOLS=", [t.name for t in tools.tools])
        result = await client.call_tool(
            "codebridge_prepare",
            {"target": "POWERSHELL5.1", "command": "Write-Output 'PHASE3_PREPARE_ONLY'"},
        )
        data = getattr(result, "structuredContent", None)
        if data is None:
            data = getattr(result, "structured_content", None)
        print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
