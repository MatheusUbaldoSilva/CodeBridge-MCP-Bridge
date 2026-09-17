import json, os, time, urllib.request, uuid
from pathlib import Path
DATA=Path(os.environ['LOCALAPPDATA'])/'CodeBridge-MCP-Bridge'
r=json.loads((DATA/'runtime.json').read_text(encoding='utf-8'))
base=f"http://{r['host']}:{r['port']}"; auth={'Authorization':f"Bearer {r['token']}"}
def post(p,o):
 h={**auth,'Content-Type':'application/json'}; q=urllib.request.Request(base+p,data=json.dumps(o).encode(),headers=h,method='POST')
 with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
def get(p):
 q=urllib.request.Request(base+p,headers=auth)
 with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
def wait_state(eid, wanted, timeout=10):
 end=time.time()+timeout
 while time.time()<end:
  s=get(f'/v1/phase5c/executions/{eid}')['execution']
  if s['state'] in wanted:return s
  time.sleep(.05)
 raise TimeoutError(eid)
def start(target,cmd,prefix):
 rid=prefix+'_'+uuid.uuid4().hex
 return post('/v1/phase5b/start',{'request_id':rid,'target':target,'command':cmd})['execution']
def cancel(target,cmd,prefix):
 first=start(target,cmd,prefix); eid=first['execution_id']
 replay=post('/v1/phase5b/start',{'request_id':first['request_id'],'target':target,'command':cmd})['execution']
 assert replay['execution_id']==eid and replay['duplicate'] is True
 wait_state(eid,{'RUNNING','FINISHED','FAILED','CANCELLED','INTERRUPTED'})
 stop=post(f'/v1/phase5d/executions/{eid}/stop',{})['stop']
 final=wait_state(eid,{'FINISHED','FAILED','CANCELLED','INTERRUPTED'})
 assert stop['cancelled'] is True and final['state']=='CANCELLED',(stop,final)
 return eid
token=uuid.uuid4().hex[:10]
ps=Path(os.environ['TEMP'])/f'cbv2_ps_{token}.txt'
cmdp=Path(os.environ['TEMP'])/f'cbv2_cmd_{token}.txt'
for p in (ps,cmdp):
 try:p.unlink()
 except FileNotFoundError:pass
ps_cmd=f"Set-Content -LiteralPath '{ps}' -Value 'start'; Start-Sleep 20; Add-Content -LiteralPath '{ps}' -Value 'end'"
cmd_cmd=f"echo start>{cmdp} && ping 127.0.0.1 -n 21 >nul && echo end>>{cmdp}"
ssh_path=f"/tmp/cbv2_ssh_{token}.txt"
ssh_cmd=f"echo start > {ssh_path} && sleep 20 && echo end >> {ssh_path}"
cancel('POWERSHELL5.1',ps_cmd,'cancel_ps')
cancel('CMD',cmd_cmd,'cancel_cmd')
cancel('SSH',ssh_cmd,'cancel_ssh')
assert ps.exists() and 'end' not in ps.read_text(errors='replace').lower(),ps.read_text(errors='replace')
assert cmdp.exists() and 'end' not in cmdp.read_text(errors='replace').lower(),cmdp.read_text(errors='replace')
probe=start('SSH',f"cat {ssh_path}",'probe_ssh'); peid=probe['execution_id']
wait_state(peid,{'FINISHED','FAILED','CANCELLED','INTERRUPTED'})
res=get(f'/v1/phase5c/executions/{peid}/result')['result']
assert res['state']=='FINISHED' and 'start' in res['output'] and 'end' not in res['output'],res
print('V2_CANCEL_EFFECTS=PASS')
