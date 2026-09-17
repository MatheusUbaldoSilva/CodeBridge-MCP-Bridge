import asyncio
import json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"
PREPARED = "req_afaf77a596fe4d7fa0fb5b56f8b200c9"

async def main():
    async with Client(URL) as client:
        result = await client.call_tool(
            "codebridge_execute_prepared",
            {"prepared_request_id": PREPARED},
        )
        data = getattr(result, "structuredContent", None)
        if data is None:
            data = getattr(result, "structured_content", None)
        print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
