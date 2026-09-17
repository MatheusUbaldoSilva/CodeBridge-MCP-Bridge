import asyncio
import json
from mcp.client.client import Client

URL = "http://127.0.0.1:8765/mcp"
CASES = [
    ("CMD", "echo PHASE4_ENTER_CONTROLLED_CMD"),
    ("SSH", "echo PHASE4_ENTER_CONTROLLED_SSH"),
]

async def structured(result):
    data = getattr(result, "structuredContent", None)
    if data is None:
        data = getattr(result, "structured_content", None)
    return data

async def main():
    async with Client(URL) as client:
        for target, command in CASES:
            prep = await client.call_tool(
                "codebridge_prepare", {"target": target, "command": command}
            )
            pdata = await structured(prep)
            print(target, "PREPARED", pdata["request_id"], pdata["enter_sent"])
            execute = await client.call_tool(
                "codebridge_execute_prepared",
                {"prepared_request_id": pdata["request_id"]},
            )
            edata = await structured(execute)
            print(target, json.dumps(edata, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
