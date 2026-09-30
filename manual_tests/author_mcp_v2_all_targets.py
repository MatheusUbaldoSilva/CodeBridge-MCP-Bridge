import asyncio, time
from mcp.client.client import Client
URL='http://127.0.0.1:8765/mcp'
async def call(c,name,args):
 r=await c.call_tool(name,args)
 d=getattr(r,'structuredContent',getattr(r,'structured_content',None))
 if d is None: raise RuntimeError(f'sem structuredContent em {name}')
 return d
async def wait(c,eid,timeout=12):
 end=time.time()+timeout
 while time.time()<end:
  s=await call(c,'codebridge_v2_status',{'execution_id':eid})
  e=s.get('execution') or {}
  if e.get('state') in {'FINISHED','FAILED','CANCELLED','INTERRUPTED'}: return e
  await asyncio.sleep(.1)
 raise TimeoutError(eid)
async def main():
 cases=[
  ('POWERSHELL5.1',"Write-Output 'MCP_PS_A'; Start-Sleep -Milliseconds 200; Write-Output 'MCP_PS_B'",['MCP_PS_A','MCP_PS_B']),
  ('CMD',"echo MCP_CMD_A & ping 127.0.0.1 -n 2 >nul & echo MCP_CMD_B",['MCP_CMD_A','MCP_CMD_B']),
  ('SSH',"echo MCP_SSH_A; sleep 1; echo MCP_SSH_B",['MCP_SSH_A','MCP_SSH_B'])]
 async with Client(URL) as c:
  tools=await c.list_tools(); names={t.name for t in tools.tools}
  needed={'codebridge_status','codebridge_v2_start','codebridge_v2_status','codebridge_v2_result','codebridge_v2_output','codebridge_v2_stop'}
  assert needed.issubset(names),(needed-names)
  status=await call(c,'codebridge_status',{})
  assert status.get('handshake_confirmed') is True and status.get('overall')=='READY',status
  for target,cmd,markers in cases:
   st=await call(c,'codebridge_v2_start',{'target':target,'command':cmd})
   assert st.get('handshake_confirmed') is True,st
   eid=st['execution']['execution_id']
   final=await wait(c,eid)
   result=await call(c,'codebridge_v2_result',{'execution_id':eid})
   out=result['execution'].get('output','')
   print(target,final.get('state'),repr(out))
   assert result.get('handshake_confirmed') is True
   assert final.get('state')=='FINISHED',final
   assert all(m in out for m in markers),(target,out)
  stoprun=await call(c,'codebridge_v2_start',{'target':'SSH','command':"echo MCP_STOP_START; sleep 20; echo MCP_STOP_END"})
  seid=stoprun['execution']['execution_id']; await asyncio.sleep(.6)
  stopped=await call(c,'codebridge_v2_stop',{'execution_id':seid})
  assert stopped.get('handshake_confirmed') is True and stopped['stop'].get('cancelled') is True,stopped
  sf=await wait(c,seid)
  assert sf.get('state')=='CANCELLED',sf
  print('AUTHOR_MCP_V2_ALL_TARGETS=PASS')
asyncio.run(main())
