import asyncio
import json
import os
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from public_token import ensure_token

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CodeBridge-MCP-Bridge"
STATE = json.loads((DATA_DIR / "public_mcp_state.json").read_text(encoding="utf-8"))
URL = STATE["mcp_url"]


async def main():
    token = ensure_token()
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http:
        async with streamable_http_client(URL, http_client=http) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [tool.name for tool in tools.tools]
                print("PUBLIC_TOOLS", len(names), "codebridge_status" in names, "codebridge_v2_start" in names)
                result = await session.call_tool("codebridge_status", {})
                data = getattr(result, "structuredContent", getattr(result, "structured_content", None))
                print("PUBLIC_STATUS", json.dumps(data, ensure_ascii=False))
                assert data.get("handshake_confirmed") is True
                assert data.get("overall") == "READY"
                print("PUBLIC_BEARER_MCP=PASS")


asyncio.run(main())
