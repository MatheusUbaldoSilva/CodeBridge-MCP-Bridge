import asyncio
import json
from mcp.client.client import Client
from runtime_client import _load_runtime, _post_json

URL = 'http://127.0.0.1:8765/mcp'

def set_auto(enabled):
    r = _load_runtime()
    url = f"http://{r['host']}:{int(r['port'])}/v1/settings/auto"
    return _post_json(url, r['token'], {'enabled': bool(enabled)})

async def call(client, name, args):
    result = await client.call_tool(name, args)
    data = getattr(result, 'structuredContent', None)
    if data is None:
        data = getattr(result, 'structured_content', None)
    return data

async def main():
    async with Client(URL) as client:
        tools = await client.list_tools()
        print('TOOLS=', [t.name for t in tools.tools])
        set_auto(False)
        off = await call(client, 'codebridge_terminal', {
            'target':'POWERSHELL5.1', 'command':"Write-Output 'MCP_AUTO_OFF_VISIBLE'"
        })
        print('AUTO_OFF=', json.dumps(off, ensure_ascii=False))
        discarded = await call(client, 'codebridge_discard', {
            'request_id': off['request_id']
        })
        print('DISCARD=', json.dumps(discarded, ensure_ascii=False))
        set_auto(True)
        on = await call(client, 'codebridge_terminal', {
            'target':'CMD', 'command':'echo MCP_AUTO_ON_EXECUTED'
        })
        print('AUTO_ON=', json.dumps(on, ensure_ascii=False))
        status = await call(client, 'codebridge_status', {})
        print('STATUS=', json.dumps(status, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
