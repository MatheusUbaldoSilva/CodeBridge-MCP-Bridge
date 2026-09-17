import json, os, time, urllib.request
from pathlib import Path
DATA=Path(os.environ['LOCALAPPDATA'])/'CodeBridge-MCP-Bridge'
r=json.loads((DATA/'runtime.json').read_text(encoding='utf-8'))
base=f"http://{r['host']}:{r['port']}"
auth={'Authorization':f"Bearer {r['token']}"}
def post(path,obj):
    h={**auth,'Content-Type':'application/json; charset=utf-8'}
    q=urllib.request.Request(base+path,data=json.dumps(obj).encode('utf-8'),headers=h,method='POST')
    with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
def get(path):
    q=urllib.request.Request(base+path,headers=auth)
    with urllib.request.urlopen(q,timeout=10) as x:return json.loads(x.read())
cases=[
 ('POWERSHELL5.1',"Write-Output 'V2_PS_A'; Start-Sleep -Milliseconds 300; Write-Output 'V2_PS_B'",['V2_PS_A','V2_PS_B']),
 ('CMD',"echo V2_CMD_A & ping 127.0.0.1 -n 2 >nul & echo V2_CMD_B",['V2_CMD_A','V2_CMD_B']),
 ('SSH',"echo V2_SSH_A; sleep 1; echo V2_SSH_B",['V2_SSH_A','V2_SSH_B'])]
for target,cmd,need in cases:
    rid='v2_'+target.replace('.','').lower()+'_'+str(time.time_ns())
    st=post('/v1/phase5b/start',{'request_id':rid,'target':target,'command':cmd})['execution']
    eid=st['execution_id']; cursor=0; output=''; final=None
    for _ in range(80):
        chunk=get(f'/v1/phase5f/executions/{eid}/output?cursor={cursor}&max_chars=4096')['output']
        output += chunk.get('text','')
        cursor = int(chunk.get('next_cursor',cursor))
        final=get(f'/v1/phase5c/executions/{eid}')['execution']
        if final.get('complete') and not chunk.get('has_more'):
            break
        time.sleep(.1)
    result=get(f'/v1/phase5c/executions/{eid}/result')['result']
    print(target,'STATE',result['state'],'EXIT',result.get('exit_code'),'OUTPUT',repr(output))
    assert result['state']=='FINISHED', result
    assert result.get('exit_code')==0, result
    assert all(x in output for x in need), (target,output)
print('V2_ALL_TARGETS_LOCAL=PASS')
