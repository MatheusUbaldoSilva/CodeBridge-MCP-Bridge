[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$name='CodeBridge_P9B_Python_Boot_Diagnostic'
$python=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
$folder=$null
$created=$false
try {
  if(!(Test-Path -LiteralPath $python -PathType Leaf)){throw 'PYTHON_MISSING'}
  if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'TASK_ALREADY_EXISTS'}
  $folder=Join-Path $env:TEMP ('cb_p9b_pythonboot_'+[guid]::NewGuid().ToString('N'))
  New-Item -Path $folder -ItemType Directory|Out-Null
  $worker=Join-Path $folder 'worker.py'
  $repo=(Get-Location).Path
  @"
import json,os,sys,time,traceback
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,r'$repo')
(root/'boot.json').write_text(json.dumps({'pid':os.getpid(),'cwd':os.getcwd(),'sys_path':sys.path[:3]}),encoding='utf-8')
try:
    from installer.rag_p9b_scheduled_combined_retry_adapter import run_lab_retry
    (root/'import.json').write_text(json.dumps({'ok':True,'utc':time.time()}),encoding='utf-8')
except Exception:
    (root/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
    sys.exit(23)
"@ | Set-Content -LiteralPath $worker -Encoding UTF8
  $action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$worker+'"') -WorkingDirectory (Get-Location).Path
  $trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(20)
  $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings|Out-Null
  $created=$true
  $xml=Export-ScheduledTask -TaskName $name
  $observations=@()
  for($i=0;$i -lt 90;$i++){
    if($i % 10 -eq 0){
      $info=Get-ScheduledTaskInfo -TaskName $name
      $observations+=@{elapsed=$i; state=[string](Get-ScheduledTask -TaskName $name).State;
        last_result=[string]$info.LastTaskResult;boot=(Test-Path (Join-Path $folder 'boot.json'))}
    }
    if((Test-Path (Join-Path $folder 'import.json')) -or (Test-Path (Join-Path $folder 'error.txt'))){break}
    Start-Sleep -Seconds 1
  }
  $summary=@{state='BOOT_DIAGNOSTIC_UNPROVEN';boot_exists=Test-Path (Join-Path $folder 'boot.json');
    import_exists=Test-Path (Join-Path $folder 'import.json');error_exists=Test-Path (Join-Path $folder 'error.txt');
    observations=$observations;xml_has_trigger=($xml -match '<TimeTrigger>');production_modified=$false}
  if($summary.error_exists){$summary.error=Get-Content -LiteralPath (Join-Path $folder 'error.txt') -Raw}
  if($summary.import_exists){$summary.state='SCHEDULED_PYTHON_IMPORT_CONFIRMED'}
  $summary|ConvertTo-Json -Compress -Depth 6
  if(!$summary.import_exists){throw 'SCHEDULED_PYTHON_IMPORT_UNVERIFIED'}
}finally {
  if($created){
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if($task -and $task.State -eq 'Running'){Stop-ScheduledTask -TaskName $name}
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
  }
  if($folder -and (Test-Path $folder)){Remove-Item -LiteralPath $folder -Recurse -Force}
}