import asyncio
import json
from mcp.client.client import Client


async def main():
    async with Client("http://127.0.0.1:8767/mcp") as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        print("TOOLS=", names)
        result = await client.call_tool("codebridge_status", {})
        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        print(json.dumps(structured, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
