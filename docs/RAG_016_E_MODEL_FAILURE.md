# RAG-016-E — Falha do modelo sem derrubar o executor MCP

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Provar a regra permanente

`Nenhum modelo pode ser requisito para o executor MCP funcionar`

Requisito do handoff

`Executor MCP deve continuar operacional`

## Estratégia

A prova foi feita em três etapas

1. confirmar CodeBridge em READY antes da falha
2. provocar falhas deliberadas de carga em Text e Code
3. confirmar READY e executar novo comando no PowerShell pelo próprio CodeBridge depois das falhas

## Falha deliberada

Criado

`rag/benchmark/model_failure.py`

API

`run_model_failure_canary()`

O canary aponta os lifecycles para artifacts propositalmente inexistentes em diretório temporário

Nenhum modelo real é alterado

Nenhum arquivo de produção é renomeado ou corrompido

## Resultado Text

```text
model_kind = TEXT
expected_error = text model artifact is missing or failed pinned verification
final_state = UNLOADED
process_alive = false
pid = null
```

A falha ocorreu fechada antes de iniciar um processo órfão

## Resultado Code

```text
model_kind = CODE
expected_error = code model artifact is missing or failed pinned verification
final_state = UNLOADED
process_alive = false
pid = null
```

O mesmo comportamento fail-closed foi observado

## Estado do CodeBridge depois da falha

A chamada real `codebridge_status` retornou

```text
overall = READY
api_online = true
PowerShell online = true
CMD online = true
SSH online = true
executor.running = true
executor.active_job_id = null
```

Portanto o erro do backend RAG não alterou o estado operacional do executor MCP

## Execução real pós-falha

Depois das duas falhas foi enviado pelo próprio CodeBridge

```text
Write-Output 'RAG016E_EXECUTOR_AFTER_OK'
```

Resultado

```text
state = FINISHED
exit_code = 0
output = RAG016E_EXECUTOR_AFTER_OK
```

Essa é a prova operacional principal

Não é apenas health check

O executor recebeu um comando novo e o concluiu depois da falha dos modelos

## Separação arquitetural provada

```text
MCP executor
│
├── PowerShell/CMD/SSH
│
└── RAG
    ├── Text model
    └── Code model
```

Se Text e Code falham

```text
RAG model path = falha
MCP executor = continua READY
terminal command = continua FINISHED / exit 0
```

Logo os modelos são capacidade auxiliar e não dependência de bootstrap do executor

## Cleanup

As falhas terminaram em

`UNLOADED`

com

`process_alive = false`

Nenhum `llama-server` foi deixado pelo canary

## Evidências

Runner

`benchmarks/run_rag016_model_failure.py`

Resultado do modelo

`benchmarks/rag016_model_failure_latest.json`

Evidência de sobrevivência do executor

`benchmarks/rag016_executor_survival_latest.json`

## Teste automático

Criado

`tests/test_rag_016_model_failure.py`

O teste exige para Text e Code

- ModelLoadError esperado
- estado final UNLOADED
- process_alive false
- PID ausente

Resultado focado

```text
Ran 1 test
OK
```

## Observação sobre a ferramenta

Durante a prova houve um prepared request antigo preso no CodeBridge

Ele foi descartado explicitamente com

`codebridge_discard`

Depois disso um novo prepare/execute foi aceito e terminou normalmente

Isso também evita confundir estado de protocolo com falha causada pelos modelos

## Arquivos

Criado

`rag/benchmark/model_failure.py`

Atualizado

`rag/benchmark/__init__.py`

Criado

`tests/test_rag_016_model_failure.py`

Criado

`benchmarks/run_rag016_model_failure.py`

Criado

`benchmarks/rag016_model_failure_latest.json`

Criado

`benchmarks/rag016_executor_survival_latest.json`

Criado

`docs/RAG_016_E_MODEL_FAILURE.md`

## Critério de aceitação

RAG-016-E está concluído quando

- Text model falha deliberadamente
- Code model falha deliberadamente
- falhas retornam a UNLOADED
- nenhum processo de modelo fica vivo
- CodeBridge continua READY
- executor continua running
- terminais continuam online
- novo comando PowerShell termina FINISHED
- novo comando retorna exit code 0
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-016-F — Auditoria Git`

Executar a política formal de fechamento do marco
