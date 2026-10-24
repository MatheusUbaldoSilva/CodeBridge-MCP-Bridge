[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$name='CodeBridge_P9B_Durable_Terminal_Lab'
$python=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
$folder=$null
$created=$false
$summary=@{}
try {
  if(!(Test-Path $python -PathType Leaf)){throw 'PYTHON_NOT_FOUND'}
  if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'REFUSE_PREEXISTING_TASK'}
  $folder=Join-Path $env:TEMP ('cb_p9b_terminal_'+[guid]::NewGuid().ToString('N'))
  New-Item -Path $folder -ItemType Directory|Out-Null
  $worker=Join-Path $folder 'worker.py'
  $repo=(Get-Location).Path.Replace('\','/')
  @"
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,r'$repo')
from installer.rag_p9b_recovery_retry_ledger import reserve_disposable_retry,mark_disposable_retry_terminal
root=Path(__file__).resolve().parent
marker=root/'first.json'
done=root/'done.json'
third=root/'third.json'
ledger=root/'retry-ledger.json'
sha='a'*64
result=reserve_disposable_retry(ledger,transaction_sha256=sha,temp_root=root)
if result.get('reserved') is True and result['attempt']==1:
    with marker.open('xb') as f:
        f.write(json.dumps({'first_pid':os.getpid(),'attempt':1,'exit':87}).encode())
        f.flush()
        os.fsync(f.fileno())
    os._exit(87)
if result.get('reserved') is True and result['attempt']==2:
    proof=mark_disposable_retry_terminal(ledger,transaction_sha256=sha,temp_root=root,postverified=True)
    if proof.get('state')!='P9B_TERMINAL_PERSISTED':
        sys.exit(15)
    with done.open('xb') as f:
        f.write(json.dumps({'second_pid':os.getpid(),'attempt':2,'terminal':True}).encode())
        f.flush()
        os.fsync(f.fileno())
    sys.exit(0)
if result.get('state')=='P9B_RECOVERY_ALREADY_TERMINAL':
    with third.open('xb') as f:
        f.write(json.dumps({'third_pid':os.getpid(),'denied':True,'reason':result.get('reason')}).encode())
        f.flush()
        os.fsync(f.fileno())
    sys.exit(0)
sys.exit(16)
"@|Set-Content -LiteralPath $worker -Encoding UTF8
  $action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$worker+'"') -WorkingDirectory $folder
  $trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(22) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Minutes 4)
  $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  $settings=New-ScheduledTaskSettingsSet -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
  $created=$true
  $xml=Export-ScheduledTask -TaskName $name
  $summary.xml_restart_count=($xml -match '<Count>2</Count>')
  $summary.xml_restart_interval=($xml -match '<Interval>PT1M</Interval>')
  $summary.xml_trigger=($xml -match '<TimeTrigger>')
  $summary.xml_repeat=($xml -match '<Repetition>')
  $observations=@()
  for($i=0;$i -lt 230;$i++){
    $info=Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if($i % 10 -eq 0){
      $observations+=@{seconds=($i*1);state=[string]$task.State;
        last_result=[string]$info.LastTaskResult;
        runs=[string]$info.NumberOfMissedRuns;
        first=(Test-Path (Join-Path $folder 'first.json'));
        second=(Test-Path (Join-Path $folder 'done.json'))}
    }
    if(Test-Path (Join-Path $folder 'third.json')){break}
    Start-Sleep -Seconds 1
  }
  $summary.first_exists=Test-Path (Join-Path $folder 'first.json')
  $summary.second_exists=Test-Path (Join-Path $folder 'done.json')
  $summary.third_exists=Test-Path (Join-Path $folder 'third.json')
  $summary.last_result=[string](Get-ScheduledTaskInfo -TaskName $name).LastTaskResult
  if($summary.first_exists -and $summary.second_exists -and $summary.third_exists){
    $first=Get-Content -LiteralPath (Join-Path $folder 'first.json') -Raw|ConvertFrom-Json
    $second=Get-Content -LiteralPath (Join-Path $folder 'done.json') -Raw|ConvertFrom-Json
    $third=Get-Content -LiteralPath (Join-Path $folder 'third.json') -Raw|ConvertFrom-Json
    $ledger=Get-Content -LiteralPath (Join-Path $folder 'retry-ledger.json') -Raw|ConvertFrom-Json
    if($first.attempt -ne 1 -or $first.exit -ne 87 -or
       $second.attempt -ne 2 -or $second.terminal -ne $true -or
       $third.denied -ne $true -or $third.reason -ne 'DURABLE_TERMINAL_STATE' -or
       $ledger.attempts -ne 2 -or $ledger.state -ne 'TERMINAL' -or
       $first.first_pid -eq $second.second_pid -or
       $third.third_pid -eq $second.second_pid){
      throw 'DURABLE_TERMINAL_PROOF_INVALID'
    }
    $summary.persisted_attempts=$ledger.attempts
    $summary.terminal_state=$ledger.state
    $summary.three_distinct_invocations=$true
  }
  $summary.observations=$observations
  $summary.production_modified=$false
  $summary.state=if($summary.second_exists){'PERIODIC_DURABLE_TERMINAL_VERIFIED'}else{'PERIODIC_AUTO_RETRY_UNPROVEN'}
  if($summary.first_exists -ne $true -or $summary.second_exists -ne $true -or $summary.third_exists -ne $true -or
     $summary.xml_repeat -ne $true -or $summary.last_result -ne '0'){
    throw ('AUTOMATIC_PERIODIC_RETRY_UNVERIFIED '+($summary|ConvertTo-Json -Compress -Depth 8))
  }
  $summary|ConvertTo-Json -Compress -Depth 8
}finally{
  if($created){
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if($task -and $task.State -eq 'Running'){
      Stop-ScheduledTask -TaskName $name -ErrorAction Stop
      for($j=0;$j -lt 20 -and (Get-ScheduledTask -TaskName $name).State -eq 'Running';$j++){
        Start-Sleep -Milliseconds 250
      }
      if((Get-ScheduledTask -TaskName $name).State -eq 'Running'){
        throw 'TASK_STILL_RUNNING_CLEANUP_REFUSED'
      }
    }
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
  }
  if($folder -and (Test-Path $folder)){
    Remove-Item -LiteralPath $folder -Recurse -Force
  }
}