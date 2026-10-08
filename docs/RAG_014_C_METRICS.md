# RAG-014-C — Métricas do benchmark

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Estado

`RAG-014-C EM PROGRESSO`

A infraestrutura de medição está pronta

Foi executado um baseline lexical real com corpus autorizado e chunking de produção

O resultado ainda não é usado como prova de qualidade semântica porque o índice persistente de produção continua vazio e o executor semântico de produção ainda não está registrado

## Métricas exigidas pelo handoff

RAG-014-C exige medir

- Recall@5
- Recall@10
- MRR
- latência cold
- latência warm
- RAM
- VRAM
- tamanho do índice

Todas essas métricas já possuem suporte de coleta no harness

## Harness

Criado

`rag/benchmark/metrics.py`

Métricas de retrieval

`evaluate_ranked_paths()`

Contrato

`RetrievalMetrics`

Campos

```text
query_count
recall_at_5
recall_at_10
mrr
```

## Medição de recursos

Criado suporte para

- RSS do processo atual
- VRAM device-wide via nvidia-smi quando disponível
- tamanho total de arquivos do índice

RAM no Windows usa

`GetProcessMemoryInfo`

via ctypes

Nenhuma dependência nova é exigida somente para benchmark

## Corpus lexical de benchmark

Criado

`rag/benchmark/corpus.py`

O corpus usa componentes reais do projeto

- `plan_rag_index`
- denylist real
- allowlist real
- `chunk_markdown`
- `chunk_text_log`
- `safe_chunk_code`
- IDs determinísticos
- SQLite oficial
- FTS5 oficial
- ranking lexical oficial

Paths principais usados

```text
rag
author_mcp
docs
```

RAW negado não é incluído

## Integridade do ground truth

Antes da medição foi detectado que quatro perguntas do bucket logs apontavam somente para arquivos RAW negados

Isso foi corrigido no commit

`e205317 fix(rag-014): require retrievable benchmark ground truth`

Depois da correção

```text
UNRETRIEVABLE 0
[]
```

Portanto todas as 100 perguntas possuem ao menos uma fonte esperada que pode realmente entrar no índice autorizado

## Baseline lexical executado

Runner

`benchmarks/run_rag014_lexical_baseline.py`

Resultado versionável

`benchmarks/rag014_lexical_baseline_latest.json`

Corpus observado

```text
documents=177
chunks=6901
denied=2966
unsupported=2
```

## Qualidade lexical observada

```text
query_count=100
Recall@5=0.000
Recall@10=0.000
MRR=0.000
```

Esse resultado não é um bug na fórmula de métricas

O caminho FTS5 atual usa literal phrase semantics para a query inteira

As 100 perguntas do benchmark são perguntas naturais e não frases copiadas literalmente dos arquivos

Portanto o baseline demonstra exatamente por que o fallback lexical sozinho não pode ser tratado como prova de qualidade do RAG

## Latência lexical observada

Execução mais recente

```text
index_build_ms=1228.4272
cold_query_ms=0.8009
warm_query_mean_ms=0.1150
warm_query_median_ms=0.08765
warm_query_p95_ms=0.2261
```

Esses valores medem somente o baseline lexical local

Não incluem

- load de modelo
- embedding de query
- busca vetorial
- troca TEXT/CODE
- RRF híbrido

Logo não podem ser publicados como latência final do RAG híbrido

## Recursos observados

```text
RAM RSS=38805504 bytes
VRAM device-wide=137 MiB
índice SQLite lexical=11653120 bytes
```

Convertendo aproximadamente

```text
RAM RSS ≈ 37.0 MiB
índice lexical ≈ 11.1 MiB
```

A VRAM de 137 MiB é somente o estado device-wide observado durante esse baseline

Nenhum modelo semântico foi carregado pelo runner

## Estado do índice persistente de produção

Auditoria imediatamente anterior ao benchmark

```text
state=EMPTY
manifest_exists=false
manifest_entries=0
sqlite_exists=false
qdrant_exists=false
```

Modelos

```text
text installed=true
code installed=true
```

Backend vetorial

```text
QDRANT_LOCAL
qdrant-client 1.19.1
```

## Bloqueio real encontrado

A superfície MCP possui `codebridge_rag_index`

Porém o bridge de produção mantém o executor de indexação como callback opcional

`_RAG_INDEX_EXECUTOR`

e não existe registro de executor de produção no runtime atual

Da mesma forma o search service aceita executor semântico opcional

Sem ele a busca cai explicitamente para

`LEXICAL_ONLY`

Por isso fechar RAG-014-C agora como benchmark híbrido seria incorreto

## O que já está provado

- cálculo de Recall@5 correto
- cálculo de Recall@10 correto
- cálculo de MRR correto
- coleta de cold latency
- coleta de warm latency
- coleta de RAM
- coleta de VRAM
- coleta de tamanho de índice
- construção real de corpus lexical
- chunking real
- FTS5 real
- 100 queries reais
- ground truth recuperável
- baseline lexical executado

## O que ainda falta para fechar RAG-014-C

Executar as mesmas 100 queries pelo caminho semântico/híbrido real

Isso exige primeiro um índice persistente válido com

- SQLite FTS5
- Qdrant text
- Qdrant code

e executor semântico real conectado ao search service

Somente depois serão registrados

- Recall@5 híbrido
- Recall@10 híbrido
- MRR híbrido
- cold latency híbrida
- warm latency híbrida
- RAM com modelos
- VRAM com modelos
- tamanho SQLite + Qdrant

## Regra

O baseline lexical fica preservado como controle

Ele não será renomeado nem reinterpretado como resultado semântico

RAG-014-C permanece aberto até existir medição híbrida real
