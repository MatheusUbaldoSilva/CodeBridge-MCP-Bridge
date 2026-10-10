param([switch]$NoPause)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:TEMP 'CodeBridge-RAG017-NativeDeps-20261010\Scripts\python.exe'
$payload = Join-Path $env:TEMP 'CodeBridge-RAG017-Isolated-Retest-20261010'
$index = Join-Path $env:TEMP 'CodeBridge-RAG017-Qdrant-Probe-20261010'
Write-Host 'CodeBridge MCP RAG - LABORATORIO EXPERIMENTAL' -ForegroundColor Cyan
Write-Host 'Somente diagnostico, sem inicializar servidor ou atualizar o CodeBridge.'
if(-not (Test-Path -LiteralPath $python)){Write-Host 'Ambiente temporario ausente.' -ForegroundColor Yellow; exit 2}
if(-not (Test-Path -LiteralPath $payload)){Write-Host 'Payload temporario ausente.' -ForegroundColor Yellow; exit 2}
& $python (Join-Path $root 'benchmarks\rag017_isolated_embedded_probe.py') --payload $payload
$probeExit=$LASTEXITCODE
if(Test-Path -LiteralPath $index){
 & $python (Join-Path $root 'benchmarks\rag017_qdrant_isolated_persistence.py') read --dir $index
 $qdrantExit=$LASTEXITCODE
}else{$qdrantExit=2;Write-Host 'Indice de teste nao encontrado.' -ForegroundColor Yellow}
$listener=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
Write-Host ('MCP principal na porta 8765: '+[bool]$listener)
Write-Host ('Resultado: dependencies='+$probeExit+', qdrant_read='+$qdrantExit)
Write-Host 'RAG-017-J BLOQUEADO para producao.' -ForegroundColor Yellow
if(-not $NoPause){Read-Host 'Pressione Enter para fechar' | Out-Null}
if($probeExit -ne 0 -or $qdrantExit -ne 0){exit 2}
exit 0
