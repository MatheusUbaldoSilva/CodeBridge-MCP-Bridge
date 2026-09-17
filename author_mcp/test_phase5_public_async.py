import asyncio, json, time
from mcp.client.client import Client
URL='https://3ff3-189-15-127-8.ngrok-free.app/mcp'
async def call(name,args):
    async with Client(URL) as client:
        r=await client.call_tool(name,args)
        return getattr(r,'structuredContent',getattr(r,'structured_content',None))
async def main():
    start=await call('codebridge_start',{'target':'POWERSHELL5.1','command':"Write-Output 'PUB5_A'; Start-Sleep 2; Write-Output 'PUB5_B'"})
    print('START',json.dumps(start,ensure_ascii=False))
    e=(start.get('execution') or {}); eid=e.get('execution_request_id'); assert eid
    cursor=0; out=''; t=time.perf_counter()
    for i in range(30):
        s=await call('codebridge_execution_status',{'execution_id':eid,'cursor':cursor,'max_chars':4096})
        ex=s.get('execution') or {}; delta=ex.get('output_delta',''); out+=delta; cursor=ex.get('output_cursor',cursor)
        print('POLL',i,ex.get('state'),'DELTA',repr(delta))
        if ex.get('complete'): break
        await asyncio.sleep(.25)
    print('ELAPSED',round(time.perf_counter()-t,3),'OUT',repr(out))
    assert ex.get('state')=='FINISHED' and 'PUB5_A' in out and 'PUB5_B' in out
    print('PHASE5_PUBLIC_ASYNC=PASS')
asyncio.run(main())