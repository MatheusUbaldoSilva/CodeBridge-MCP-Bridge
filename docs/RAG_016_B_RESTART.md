# RAG-016-B — Restart real do CodeBridge

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Provar recuperação do RAG e do executor depois de fechar e reabrir o CodeBridge

Requisito do handoff

`Provar recuperação após fechar/reabrir CodeBridge`

## Estratégia

O teste foi dividido em três provas independentes

1 preparar um índice RAG persistente antes do restart
2 fechar e reabrir o aplicativo CodeBridge de verdade
3 abrir o mesmo índice em processo novo e comparar com o baseline

Também foi executado um comando real pelo MCP depois do restart

## Probe persistente

Criado

`rag/benchmark/restart.py`

APIs

`prepare_restart_probe()`

`verify_restart_probe()`

O prepare cria em diretório persistente temporário

```text
restart.sqlite3
qdrant/
restart-baseline.json
```

O verify abre esses mesmos artefatos novamente sem reindexar e exige igualdade integral com o baseline

## Baseline antes do restart

Execução

`benchmarks/run_rag016_restart_probe.py prepare`

Resultado

```text
project_id = codebridge
documents = 190
chunks = 7639
text_vector_points = 1
code_vector_points = 1
query_text = RAG 014 B
signature = 8 chunk IDs
```

A conexão SQLite e o Qdrant foram fechados antes do restart

Logo a prova posterior não depende de handles abertos do processo anterior

## Restart real do aplicativo

Antes

```text
author MCP 8765 PID 2752
executor   8766 PID 2328
main       8768 PID 1720
```

O primeiro fechamento por canal auxiliar recebeu `Access denied`

Isso confirmou que o CodeBridge estava rodando em nível de privilégio superior

Nenhum processo foi alterado nessa tentativa

O restart então foi disparado pelo próprio executor CodeBridge usando um helper PowerShell destacado no mesmo nível de privilégio do app

## Evidência de fechamento

O helper registrou

```text
executor_closed = true
main_closed = true
```

Portanto os listeners locais de executor e companion realmente desapareceram antes da reabertura

Não foi apenas refresh de UI

## Evidência de reabertura

Depois

```text
executor 8766 PID 12340
main     8768 PID 12452
```

Ambos os PIDs mudaram

```text
executor_pid_changed = true
main_pid_changed = true
```

Health após reabrir

```text
8766 /health  -> ok true protocol CBMCP/1
8768 /healthz -> ok true service chatgpt-companion
```

## MCP autoral

Durante o fechamento do app o listener 8765 ainda estava no PID 2752

Na reabertura o CodeBridge substituiu esse processo por

`PID 9612`

Logo o restart acabou renovando também o MCP autoral

Isso é mais forte que a hipótese inicial de preservá-lo

Depois da troca a conexão ChatGPT -> CodeBridge se recuperou automaticamente

## Status real depois do restart

A chamada `codebridge_status` retornou

```text
protocol = CBMCP/1
handshake_confirmed = true
app = CodeBridge 2.0 - MCP Bridge
version = 2.0.11-prealpha
overall = READY
api_online = true
PowerShell online = true
CMD online = true
SSH online = true
executor running = true
execution_generation = 0
```

O `execution_generation = 0` é consistente com um executor recém-criado

## Execução real pós-restart

Foi enviado pelo CodeBridge

```text
Write-Output 'RAG016_POST_RESTART_EXECUTOR_OK'
Write-Output ('PID=' + $PID)
```

Resultado

```text
RAG016_POST_RESTART_EXECUTOR_OK
PID=7768
exit_code=0
state=FINISHED
```

Assim o teste não se limita a health endpoint

O executor realmente voltou a executar comandos depois do restart

## Recuperação do RAG

Depois do restart foi iniciado um processo Python novo e executado

`benchmarks/run_rag016_restart_probe.py verify`

Resultado

```text
documents = 190
chunks = 7639
text_vector_points = 1
code_vector_points = 1
query_text = RAG 014 B
signature = os mesmos 8 chunk IDs
```

O objeto observado ficou exatamente igual ao baseline

Qualquer divergência de

- documents
- chunks
- vector counts
- query
- ranking/signature

faz `verify_restart_probe()` falhar

## Evidências versionadas

`benchmarks/rag016_restart_baseline.json`

baseline criado antes do restart

`benchmarks/rag016_app_restart_latest.json`

PIDs fechamento reabertura e health

`benchmarks/rag016_restart_latest.json`

verificação executada depois do restart

## Teste automático

Criado

`tests/test_rag_016_restart.py`

Ele prova

- prepare persiste SQLite Qdrant e baseline
- verify abre storage novamente
- resultado observado é idêntico ao baseline
- baseline ausente falha explicitamente

Resultado observado

```text
Ran 2 tests in 0.777s
OK
```

## Arquivos

Criado

`rag/benchmark/restart.py`

Atualizado

`rag/benchmark/__init__.py`

Criado

`tests/test_rag_016_restart.py`

Criado

`benchmarks/run_rag016_restart_probe.py`

Criado

`benchmarks/rag016_restart_baseline.json`

Criado

`benchmarks/rag016_app_restart_latest.json`

Atualizado

`benchmarks/rag016_restart_latest.json`

Criado

`docs/RAG_016_B_RESTART.md`

## Critério de aceitação

RAG-016-B está concluído quando

- índice persistente existe antes do restart
- handles são fechados antes da prova
- CodeBridge main realmente fecha
- executor realmente fecha
- CodeBridge main abre com PID novo
- executor abre com PID novo
- health volta OK
- handshake MCP volta confirmado
- comando pós-restart termina com exit code 0
- SQLite é recuperado
- Qdrant é recuperado
- assinatura de retrieval permanece idêntica
- testes passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-016-C — CPU-only`

Executar canário do stack RAG sem GPU dedicada usando fallback explícito em CPU
