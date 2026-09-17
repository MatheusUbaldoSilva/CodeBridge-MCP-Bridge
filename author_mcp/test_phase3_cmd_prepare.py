import asyncio, json
from mcp.client.client import Client

async def main():
    async with Client('http://127.0.0.1:8765/mcp') as client:
        tools=await client.list_tools()
        print('TOOLS=', [t.name for t in tools.tools])
        r=await client.call_tool('codebridge_prepare', {'target':'CMD','command':'echo PHASE3_CMD_PREPARE_ONLY'})
        data=getattr(r,'structuredContent',None) or getattr(r,'structured_content',None)
        print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__': asyncio.run(main())