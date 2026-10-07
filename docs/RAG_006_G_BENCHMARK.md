# RAG-006-G — Benchmark de custo

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Registrar o custo real do modelo textual em GPU e CPU para fechar o RAG-006

Métricas exigidas pelo handoff

- RAM
- VRAM
- cold start
- warm query
- embeddings/s
- tempo de unload

## Metodologia

Cold start

tempo de `load()` até READY

Warm query

uma query de aquecimento descartada

depois média de 5 chamadas sequenciais de `embed_query`

Throughput

20 chamadas sequenciais de `embed_document`

batch efetivo permanece 1

RAM

Working Set do PID do `llama-server` em READY

medido por Win32 `GetProcessMemoryInfo`

sem dependência psutil

VRAM

No Windows WDDM o `nvidia-smi --query-compute-apps` deste ambiente reporta memória por processo como N/A

Portanto o benchmark registra o delta device-wide de

`nvidia-smi --query-gpu=memory.used`

antes e depois da carga

Esse delta pode conter ruído de outros processos GPU e é documentado como aproximação

Unload

tempo de `unload()` até retorno UNLOADED

## Implementação

Criado

`rag/models/benchmark.py`

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_text_benchmark.py`

O benchmark não é executado no import

Nenhum modelo é carregado sem chamada explícita


## Ambiente real medido

- Windows
- `C:\llama\llama-server.exe`
- Jina v5 Text Small Retrieval
- GGUF Q4_K_M pinado no RAG-006-B
- dimensão 1024
- batch efetivo 1
- GPU descoberta como `CUDA0`
- NVIDIA GeForce RTX 3050 6GB Laptop GPU

## Carga do benchmark

Warm query

`como funciona o carregamento sob demanda?`

Throughput

20 documentos curtos distintos no formato

`Documento benchmark numero N sobre CodeBridge RAG e embeddings locais.`

Cada modo executou

- load real
- uma query de aquecimento descartada
- 5 warm queries
- 20 document embeddings
- unload real

Cache não foi usado

## Resultado real — GPU

```text
mode=GPU
cold_start_s=1.9431970000150613
warm_query_mean_ms=27.939600020181388
embeddings_per_s=42.04669108932594
ram_bytes=822087680
vram_delta_mib=4214
unload_ms=111.36379995150492
warm_samples=5
throughput_samples=20
```

Convertendo RAM

`822087680 bytes ≈ 784.00 MiB`

## Resultado real — CPU

Modo explicitamente forçado

```text
--device none
-ngl 0
```

Resultado

```text
mode=CPU
cold_start_s=6.864230000006501
warm_query_mean_ms=26.421719987411052
embeddings_per_s=20.586995254493211
ram_bytes=5080555520
vram_delta_mib=0
unload_ms=349.91140000056475
warm_samples=5
throughput_samples=20
```

Convertendo RAM

`5080555520 bytes ≈ 4845.20 MiB ≈ 4.73 GiB`

## Comparação

| Métrica | GPU | CPU |
| --- | ---: | ---: |
| Cold start | 1.943 s | 6.864 s |
| Warm query média | 27.94 ms | 26.42 ms |
| Embeddings/s | 42.05 | 20.59 |
| RAM Working Set | 784.00 MiB | 4845.20 MiB |
| VRAM delta device-wide | 4214 MiB | 0 MiB |
| Unload | 111.36 ms | 349.91 ms |

Razões observadas

- GPU teve cold start aproximadamente 3.53 vezes mais rápido
- GPU teve throughput aproximadamente 2.04 vezes maior
- GPU teve unload aproximadamente 3.14 vezes mais rápido
- CPU teve warm query curta aproximadamente 5.7 por cento mais rápida nesta carga específica

A pequena vantagem da CPU em uma única query curta não implica maior capacidade geral

O throughput sustentado favoreceu claramente a GPU

## Interpretação de memória

GPU

O Working Set do processo ficou em aproximadamente 784 MiB

O delta de VRAM total do device foi 4214 MiB

Esse número inclui buffers/contexto/backend e pode conter ruído de outros processos porque WDDM não forneceu memória por PID neste ambiente

CPU

O Working Set chegou a aproximadamente 4.73 GiB

VRAM device-wide não aumentou durante o benchmark CPU

Isso confirma a utilidade do fallback, mas também mostra que CPU é significativamente mais cara em RAM no ambiente medido

## Correções encontradas durante a validação

O primeiro teste do harness usava monkeypatch global de `TextEmbeddingClient`

No discovery completo esse patch não se mostrou confiável

O benchmark foi melhorado para aceitar `client_factory` injetável somente como dependency injection de teste

Produção continua usando `TextEmbeddingClient` por padrão

Uma regravação intermediária do teste introduziu erro de indentação

O arquivo foi corrigido e os testes foram repetidos antes do fechamento

## Validação final

Testes específicos do benchmark

```text
Ran 3 tests
OK
```

Suíte RAG completa

```text
Ran 329 tests
OK
```

Git whitespace audit

```text
git diff --check b8a27f16075fe1b0f98de7d91f48f30a0516b7a5..HEAD
exit_code = 0
```

Worktree de validação

```text
## HEAD (no branch)
```

sem alterações locais

## Estado final do RAG-006-G

- RAM GPU registrada
- RAM CPU registrada
- VRAM GPU registrada como delta device-wide
- VRAM CPU registrada
- cold start GPU e CPU registrados
- warm query GPU e CPU registrados
- embeddings/s GPU e CPU registrados
- unload GPU e CPU registrados
- metodologia versionada
- benchmark real concluído
- 329 testes RAG passaram
- diff check passou

RAG-006-G está pronto para fechamento

Pelo critério do handoff, o RAG-006 agora possui benchmark registrado e pode seguir para closeout formal
