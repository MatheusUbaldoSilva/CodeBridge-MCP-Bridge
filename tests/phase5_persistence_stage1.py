import json, os, time, urllib.request
from pathlib import Path
D=Path(os.environ['LOCALAPPDATA'])/'CodeBridge-MCP-Bridge'; r=json.loads((D/'runtime.json').read_text())
b=f"http://{r['host']}:{r['port']}"; h={'Authorization':f"Bearer {r['token']}",'Content-Type':'application/json'}
def post(p,o):
 q=urllib.request.Request(b+p,data=json.dumps(o).encode(),headers=h,method='POST'); return json.loads(urllib.request.urlopen(q,timeout=10).read())
def get(p):
 q=urllib.request.Request(b+p,headers={'Authorization':h['Authorization']}); return json.loads(urllib.request.urlopen(q,timeout=10).read())
post('/v1/settings/auto',{'enabled':True}); rid='phase5_persist_'+str(int(time.time()*1000))
st=post('/v1/executions/start',{'request_id':rid,'target':'POWERSHELL5.1','command':"Write-Output 'PERSIST_A'; Start-Sleep 1; Write-Output 'PERSIST_B'"})['dispatch']; eid=st['execution']['execution_request_id']
cur=0; out=''
for _ in range(30):
 s=get(f'/v1/executions/{eid}?cursor={cur}&max_chars=4096')['execution']; out+=s.get('output_delta','');cur=s.get('output_cursor',cur)
 if s.get('complete'):break
 time.sleep(.2)
post('/v1/settings/auto',{'enabled':False}); assert s['state']=='FINISHED' and 'PERSIST_A' in out and 'PERSIST_B' in out
path=Path(r'C:\Users\Matheus\CodeBridge-MCP-Bridge\tests\phase5_persist_id.txt');path.write_text(eid+'\n',encoding='utf-8')
print('EXECUTION_ID='+eid);print('BEFORE_RESTART='+repr(out));print('PHASE5_PERSIST_STAGE1=PASS')