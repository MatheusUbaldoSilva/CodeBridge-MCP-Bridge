# P9-B: execute disposable combined rollback lab from an independent task.
# Only runs a fixed test suite against TemporaryDirectory and simulated HKCU.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Repository)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$task='CodeBridge_P9B_Independent_Recovery_Lab'
$python=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
$root=(Resolve-Path -LiteralPath $Repository).Path
$folder=$null
$created=$false
try {
  if (!(Test-Path -LiteralPath $python -PathType Leaf) -or
      !(Test-Path -LiteralPath (Join-Path $root 'tests\test_rag_p9b_detached_combined_hardcrash_chain_e2e.py') -PathType Leaf)) {
    throw 'LAB_DEPENDENCIES_MISSING'
  }
  if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) {
    throw 'REFUSE_PREEXISTING_TASK'
  }
  $folder=Join-Path $env:TEMP ('cb_p9b_independent_lab_'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory $folder -ErrorAction Stop|Out-Null
  $worker=Join-Path $folder 'worker.py'
  $result=Join-Path $folder 'result.json'
  @{
    repo=$root
  } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $folder 'request.json') -Encoding UTF8
  $lines=@(
    'import json,os,sys,unittest'
    'from pathlib import Path'
    'folder=Path(__file__).resolve().parent'
    'request=json.loads((folder/"request.json").read_text(encoding="utf-8-sig"))'
    'repo=Path(request["repo"]).resolve()'
    'lib=Path(os.environ["LOCALAPPDATA"])/"CodeBridge-MCP-Bridge"/"release_staging"/"P9B_HEAD_CANDIDATE_f45880511c"/"external_supervisor_lib"'
    'sys.path[:0]=[str(repo),str(lib)]'
    'from installer.rag_p9b_detached_process_ancestry import inspect_detached_process_ancestry'
    'ancestry=inspect_detached_process_ancestry(installed=Path(os.environ["LOCALAPPDATA"])/"Programs"/"CodeBridge")'
    'if ancestry.get("state")!="EXTERNAL_PROCESS_ANCESTRY_VERIFIED":'
    '    result={"state":"INDEPENDENT_LAB_REFUSED","verified":False,"reason":"ANCESTRY"}'
    'else:'
    '    suite=unittest.defaultTestLoader.discover(str(repo/"tests"),pattern="test_rag_p9b_detached_combined_hardcrash_chain_e2e.py")'
    '    with (folder/"test.log").open("w",encoding="utf-8") as stream:'
    '        run=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite)'
    '    result={"state":"SCHEDULER_ISOLATED_COMBINED_ROLLBACK_LAB","verified":run.wasSuccessful(),"passes":run.testsRun,"failures":len(run.failures),"errors":len(run.errors),"ancestry_verified":True,"production_modified":False}'
    '(folder/"result.json").write_text(json.dumps(result,sort_keys=True),encoding="utf-8")'
  )
  $lines|Set-Content -LiteralPath $worker -Encoding UTF8
  $action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$worker+'"') -WorkingDirectory $folder
  $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -ErrorAction Stop|Out-Null
  $created=$true
  Start-ScheduledTask -TaskName $task -ErrorAction Stop
  for($i=0;$i -lt 40 -and !(Test-Path -LiteralPath $result);$i++){Start-Sleep -Milliseconds 500}
  if (!(Test-Path -LiteralPath $result -PathType Leaf)){throw 'LAB_RESULT_MISSING'}
  $proof=Get-Content -LiteralPath $result -Raw|ConvertFrom-Json
  if ($proof.state -ne 'SCHEDULER_ISOLATED_COMBINED_ROLLBACK_LAB' -or
      $proof.verified -ne $true -or $proof.ancestry_verified -ne $true -or
      $proof.production_modified -ne $false -or $proof.failures -ne 0 -or
      $proof.errors -ne 0 -or $proof.passes -lt 1){throw 'LAB_FAILED_OR_UNVERIFIED'}
  [pscustomobject]@{state='SCHEDULED_COMBINED_LAB_VERIFIED';tests=$proof.passes;
    ancestry_verified=$true;production_modified=$false;nsis_executed=$false
  }|ConvertTo-Json -Compress
}finally{
  if($created){Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction Stop}
  if($folder -and (Test-Path -LiteralPath $folder)){
    Remove-Item -LiteralPath $folder -Recurse -Force -ErrorAction Stop
  }
}
