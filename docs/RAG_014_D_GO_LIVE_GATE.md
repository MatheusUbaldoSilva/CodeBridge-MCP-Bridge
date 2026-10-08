# RAG-014-D — Critério mínimo e gate de go-live

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Estado

`RAG-014-D ✅ FECHADO`

O threshold foi definido antes do go-live e aplicado ao benchmark real do RAG-014-C

## Thresholds congelados

```text
Recall@5  >= 0.80
Recall@10 >= 0.90
MRR        >= 0.60

cold latency <= 20000 ms
warm p95    <= 1000 ms

RAM peak    <= 6 GiB
VRAM delta  <= 5120 MiB
index size  <= 2 GiB
```

Além disso o gate exige que o índice persistente de produção esteja `READY`

## Resultado real comparado ao gate

Qualidade

```text
Recall@5  = 0.46   FAIL
Recall@10 = 0.48   FAIL
MRR       = 0.325778 FAIL
```

Desempenho e recursos

```text
cold estimate = 3271.871 ms PASS
warm p95      = 140.112 ms  PASS
llama peak RSS + runner < 6 GiB PASS
VRAM delta    = 4215 MiB PASS
index total   = 90600481 bytes PASS
```

Estado de produção

```text
production index = EMPTY
READY required   = yes
resultado        = FAIL
```

## Decisão

`PRODUCTION READINESS = BLOCKED`

Falhas estruturadas atuais

```text
production_index:NOT_READY
recall_at_5:BELOW_THRESHOLD:0.460000<0.800000
recall_at_10:BELOW_THRESHOLD:0.480000<0.900000
mrr:BELOW_THRESHOLD:0.325778<0.600000
```

Latência RAM VRAM e tamanho do índice não bloquearam o gate

O bloqueio atual é qualidade de retrieval mais ausência do índice persistente de produção

## Implementação

Criado

`rag/benchmark/gate.py`

Contratos

- `RagGoLiveThresholds`
- `RagGoLiveObservation`
- `RagGoLiveDecision`
- `evaluate_go_live()`

Criado

`tests/test_rag_014_gate.py`

O teste prova

- thresholds congelados
- cenário aprovado passa
- métricas ausentes bloqueiam
- qualidade abaixo do limite bloqueia
- latência acima do limite bloqueia
- RAM acima do limite bloqueia
- VRAM acima do limite bloqueia
- índice acima do limite bloqueia

## Relatório versionado

Gerador

`benchmarks/build_rag014_readiness_report.py`

Saída

`benchmarks/rag014_readiness_report.json`

O relatório preserva separadamente

- benchmark semântico real
- baseline lexical
- estado do índice persistente
- modelos
- backend
- thresholds
- falhas do gate

## Regra

RAG-014-D não autoriza reduzir thresholds depois de observar um resultado ruim apenas para produzir PASS

Qualquer alteração futura desses thresholds exige justificativa e novo benchmark

## Resultado

O marco de benchmark pode ser fechado porque medimos e decidimos de forma objetiva

O RAG ainda não pode ser declarado pronto para produção

Antes do go-live será necessário elevar qualidade e deixar o índice persistente READY
