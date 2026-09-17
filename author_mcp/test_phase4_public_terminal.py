import asyncio
import json
from mcp.client.client import Client

URL = 'https://aee7-189-15-127-8.ngrok-free.app/mcp'

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print('TOOLS=', [t.name for t in tools.tools])
        status = await client.call_tool('codebridge_status', {})
        s = getattr(status, 'structuredContent', None) or getattr(status, 'structured_content', None)
        print('STATUS=', json.dumps(s, ensure_ascii=False))
        result = await client.call_tool('codebridge_terminal', {
            'target':'POWERSHELL5.1',
            'command':"Write-Output 'PUBLIC_PHASE4_TERMINAL_OK'",
        })
        data = getattr(result, 'structuredContent', None) or getattr(result, 'structured_content', None)
        print('TERMINAL=', json.dumps(data, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
