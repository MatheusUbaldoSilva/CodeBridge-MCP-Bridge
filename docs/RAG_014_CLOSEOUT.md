# RAG-014 — Closeout do benchmark próprio do CodeBridge

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Estado

`RAG-014 ✅ FECHADO`

O marco de benchmark foi concluído com dataset versionado ground truth manual métricas reais e gate objetivo de go-live

Fechar o benchmark não significa liberar o RAG para produção

O gate atual está bloqueado

## RAG-014-A — Dataset

Commit

`a3cbefa test(rag-014-a): add real 100-query benchmark dataset`

Dataset

`benchmarks/rag014_dataset.jsonl`

Distribuição

```text
25 code
25 docs/handoffs
20 errors/audits
10 git
10 logs
10 pt-BR → code/termos em inglês
total 100
```

## RAG-014-B — Ground truth

Commit

`092434c test(rag-014-b): add manual benchmark ground truth`

Arquivo

`benchmarks/rag014_ground_truth.jsonl`

Todas as 100 queries possuem fonte esperada manual

## Correção de integridade

Commit

`e205317 fix(rag-014): require retrievable benchmark ground truth`

Quatro queries do bucket logs apontavam somente para RAW negado

Após correção

```text
UNRETRIEVABLE 0
```

## RAG-014-C — Métricas reais

Harness inicial

`e16d5b5 feat(rag-014-c): add truthful benchmark metrics harness`

Benchmark semântico real

`9bd9023 bench(rag-014-c): measure real semantic retrieval`

Corpus

```text
179 documents
6994 chunks
5959 text vectors
1035 code vectors
```

Rotas

```text
TEXT 65
CODE 30
HYBRID 5
```

Qualidade observada

```text
Recall@5  = 0.46
Recall@10 = 0.48
MRR       = 0.325778
```

Latência

```text
cold estimate = 3271.871 ms
warm mean     = 87.957 ms
warm p95      = 140.112 ms
```

Recursos

```text
llama peak RSS = 4947095552 bytes
max VRAM delta = 4215 MiB
index total    = 90600481 bytes
```

## RAG-014-D — Gate

Commit

`ae15f40 feat(rag-014-d): enforce benchmark go-live gate`

Thresholds

```text
Recall@5  >= 0.80
Recall@10 >= 0.90
MRR       >= 0.60
cold      <= 20000 ms
warm p95  <= 1000 ms
RAM       <= 6 GiB
VRAM      <= 5120 MiB
index     <= 2 GiB
production index must be READY
```

Decisão atual

`PRODUCTION READINESS = BLOCKED`

Falhas

```text
production_index:NOT_READY
recall_at_5:BELOW_THRESHOLD
recall_at_10:BELOW_THRESHOLD
mrr:BELOW_THRESHOLD
```

Latência RAM VRAM e tamanho passaram

## Validação

Antes do fechamento de RAG-014-C

```text
Ran 641 tests
OK
```

Antes do fechamento de RAG-014-D

```text
Ran 641 tests
OK
```

`git diff --check` limpo

Commits foram enviados para `origin/rag-014-benchmark`

## Artefatos principais

`benchmarks/rag014_dataset.jsonl`

`benchmarks/rag014_ground_truth.jsonl`

`benchmarks/rag014_lexical_baseline_latest.json`

`benchmarks/rag014_semantic_benchmark_latest.json`

`benchmarks/rag014_readiness_report.json`

## Regra preservada

O resultado ruim não foi transformado em PASS reduzindo threshold depois da medição

O benchmark está fechado e auditável

A produção permanece bloqueada até a qualidade subir e o índice persistente estar READY

## Próximo marco

`RAG-015 — Segurança`

Sequência

```text
RAG-015-A Secrets
RAG-015-B Escopo
RAG-015-C Path traversal
RAG-015-D Conteúdo indexado
RAG-015-E Exclusão
```

RAG-015 deve executar testes negativos antes do closeout
