import asyncio, json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"

async def main():
    async with Client(URL) as client:
        discarded = await client.call_tool("codebridge_discard", {})
        d = getattr(discarded, "structuredContent", None) or getattr(discarded, "structured_content", None)
        print("DISCARD=", json.dumps(d, ensure_ascii=False))
        prepared = await client.call_tool("codebridge_prepare", {
            "target": "SSH",
            "command": "echo PHASE3_SSH_PREPARE_ONLY",
        })
        p = getattr(prepared, "structuredContent", None) or getattr(prepared, "structured_content", None)
        print("PREPARE=", json.dumps(p, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
