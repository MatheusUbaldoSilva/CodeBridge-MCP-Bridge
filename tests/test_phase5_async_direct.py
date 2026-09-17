import json, os, time, urllib.request
from pathlib import Path
DATA=Path(os.environ['LOCALAPPDATA'])/'CodeBridge-MCP-Bridge'
r=json.loads((DATA/'runtime.json').read_text(encoding='utf-8'))
base=f"http://{r['host']}:{r['port']}"
h={'Authorization':f"Bearer {r['token']}", 'Content-Type':'application/json'}
def post(path,obj):
    req=urllib.request.Request(base+path,data=json.dumps(obj).encode(),headers=h,method='POST')
    with urllib.request.urlopen(req,timeout=10) as x:return json.loads(x.read())
def get(path):
    req=urllib.request.Request(base+path,headers={'Authorization':h['Authorization']})
    with urllib.request.urlopen(req,timeout=10) as x:return json.loads(x.read())
post('/v1/settings/auto',{'enabled':True})
cmd="Write-Output 'P5_1'; Start-Sleep -Seconds 1; Write-Output 'P5_2'; Start-Sleep -Seconds 1; Write-Output 'P5_3'"
rid='phase5_async_ps_'+str(int(time.time()*1000))
t=time.perf_counter(); start=post('/v1/executions/start',{'request_id':rid,'target':'POWERSHELL5.1','command':cmd})
print('START_ELAPSED',round(time.perf_counter()-t,3)); print('START',json.dumps(start,ensure_ascii=False))
exec_id=start['dispatch']['execution']['execution_request_id']; cursor=0; seen=''
for i in range(20):
    s=get(f'/v1/executions/{exec_id}?cursor={cursor}&max_chars=4096')['execution']
    delta=s.get('output_delta',''); seen+=delta; cursor=s.get('output_cursor',cursor)
    print('POLL',i,s['state'],'CURSOR',cursor,'DELTA',repr(delta))
    if s.get('complete'): break
    time.sleep(.3)
print('FINAL_SEEN',repr(seen))
post('/v1/settings/auto',{'enabled':False})
assert 'P5_1' in seen and 'P5_2' in seen and 'P5_3' in seen
assert s['state']=='FINISHED' and s.get('exit_code')==0
assert time.perf_counter()-t < 8
print('PHASE5_ASYNC_DIRECT_PS=PASS')