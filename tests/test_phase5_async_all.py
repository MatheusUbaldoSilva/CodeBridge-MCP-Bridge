import json, os, time, urllib.request
from pathlib import Path
DATA=Path(os.environ['LOCALAPPDATA'])/'CodeBridge-MCP-Bridge'; r=json.loads((DATA/'runtime.json').read_text())
base=f"http://{r['host']}:{r['port']}"; auth={'Authorization':f"Bearer {r['token']}"}
def post(p,o):
    h={**auth,'Content-Type':'application/json'}; q=urllib.request.Request(base+p,data=json.dumps(o).encode(),headers=h,method='POST')
    with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
def get(p):
    q=urllib.request.Request(base+p,headers=auth)
    with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
post('/v1/settings/auto',{'enabled':True})
cases=[
 ('POWERSHELL5.1',"Write-Output 'PS_A'; Start-Sleep 1; Write-Output 'PS_B'",['PS_A','PS_B']),
 ('CMD',"echo CMD_A & ping 127.0.0.1 -n 2 >nul & echo CMD_B",['CMD_A','CMD_B']),
 ('SSH',"echo SSH_A; sleep 1; echo SSH_B",['SSH_A','SSH_B'])]
for target,cmd,need in cases:
    rid='p5_'+target.replace('.','')+'_'+str(int(time.time()*1000)); t=time.perf_counter()
    st=post('/v1/executions/start',{'request_id':rid,'target':target,'command':cmd})['dispatch']; eid=st['execution']['execution_request_id']
    print(target,'START_MS',round((time.perf_counter()-t)*1000,1),st['execution']['state'])
    cursor=0; allout=''; final=None
    for _ in range(40):
        final=get(f'/v1/executions/{eid}?cursor={cursor}&max_chars=4096')['execution']; allout+=final.get('output_delta',''); cursor=final.get('output_cursor',cursor)
        if final.get('complete'): break
        time.sleep(.2)
    print(target,'FINAL',final['state'],'EXIT',final.get('exit_code'),'OUT',repr(allout))
    assert final['state']=='FINISHED' and final.get('exit_code')==0 and all(x in allout for x in need)
post('/v1/settings/auto',{'enabled':False})
print('PHASE5_ASYNC_ALL=PASS')