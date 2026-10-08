# RAG-014-C — Métricas do benchmark real

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Estado

`RAG-014-C ✅ FECHADO`

O benchmark semântico real foi executado com os componentes reais do RAG

- chunkers de produção
- SQLite + FTS5
- Qdrant Local
- Jina Text 1024D
- Jina Code 1536D
- classificador determinístico
- rotas TEXT CODE e HYBRID
- Reciprocal Rank Fusion
- deduplicação
- 100 consultas do dataset RAG-014-A
- ground truth manual do RAG-014-B

Nenhum resultado lexical foi renomeado como semântico

## Correção de integridade anterior

Antes da execução quatro consultas do bucket logs apontavam somente para RAW que a própria política de segurança impede de indexar

Correção

`e205317 fix(rag-014): require retrievable benchmark ground truth`

Auditoria após correção

```text
UNRETRIEVABLE 0
[]
```

Portanto as 100 consultas possuem pelo menos uma fonte esperada elegível para indexação

## Baseline lexical de controle

Arquivo

`benchmarks/rag014_lexical_baseline_latest.json`

O baseline usa somente FTS5 literal phrase

Resultado observado

```text
Recall@5  = 0.000
Recall@10 = 0.000
MRR       = 0.000
```

Esse baseline é preservado como controle

Ele demonstra que perguntas naturais não devem ser avaliadas como se o fallback lexical literal fosse busca semântica

## Benchmark semântico real

Runner

`benchmarks/run_rag014_semantic_benchmark.py`

Resultado

`benchmarks/rag014_semantic_benchmark_latest.json`

Tempo total observado da execução

aproximadamente 343.68 segundos

## Corpus

```text
documents   = 179
chunks      = 6994
denied      = 2967
unsupported = 2
```

Distribuição vetorial efetivamente indexada

```text
text chunks = 5959
code chunks = 1035
```

As fontes negadas continuam fora do benchmark

## Rotas das 100 consultas

```text
TEXT   = 65
CODE   = 30
HYBRID = 5
```

A rota foi definida pelo classificador determinístico do RAG-008-A

Nenhum LLM escolheu a rota

## Métricas de qualidade observadas

```text
Recall@5  = 0.460000
Recall@10 = 0.480000
MRR       = 0.325778
```

Interpretação

46 das 100 consultas encontraram pelo menos uma fonte esperada até posição 5

48 das 100 encontraram fonte esperada até posição 10

O MRR observado foi aproximadamente 0.326

Esses números são o resultado real atual

Não foram ajustados ou arredondados para parecer melhores

## Pipeline medido

```text
query
↓
classificador
├── TEXT
│   ├── FTS5
│   └── Jina Text 1024D → Qdrant
│
├── CODE
│   ├── FTS5
│   └── Jina Code 1536D → Qdrant
│
└── HYBRID
    ├── FTS5
    ├── Jina Text 1024D → Qdrant
    └── Jina Code 1536D → Qdrant

rankings
↓
RRF k=60
↓
dedup
↓
top 10
```

## Modelos reais

Text

`jinaai/jina-embeddings-v5-text-small`

Code

`jinaai/jina-code-embeddings-1.5b`

Backend

`C:\llama\llama-server.exe`

Execução observada

GPU `CUDA0`

Os modelos foram carregados sequencialmente

Não permaneceram residentes ao mesmo tempo

## Latência observada

Cold estimate

```text
3271.871 ms
```

Definição congelada para esta execução

`model load da rota da primeira query + query embedding + retrieval`

Warm end-to-end aproximado sem custo de troca de modelo

```text
mean   = 87.957 ms
median = 81.823 ms
p95    = 140.112 ms
```

Retrieval após embedding

```text
mean = 53.681 ms
```

Query embedding

```text
Jina Text mean = 27.298 ms
Jina Code mean = 43.334 ms
```

Model load durante fase de queries

```text
Text = 2424.971 ms
Code = 3046.665 ms
```

Observação HYBRID

A métrica warm soma os dois embeddings e o retrieval

O custo de trocar fisicamente TEXT → CODE não foi escondido

Ele permanece separado nos tempos de model load

## Indexação vetorial real

### Text

```text
chunks                  = 5959
model load              = 1948.326 ms
embedding + Qdrant      = 220857.116 ms
llama peak RSS          = 4195241984 bytes
VRAM before             = 137 MiB
VRAM loaded             = 4352 MiB
VRAM after unload       = 137 MiB
VRAM delta              = 4215 MiB
```

### Code

```text
chunks                  = 1035
model load              = 5163.275 ms
embedding + Qdrant      = 97056.710 ms
llama peak RSS          = 4947095552 bytes
VRAM before             = 137 MiB
VRAM loaded             = 3254 MiB
VRAM after unload       = 137 MiB
VRAM delta              = 3117 MiB
```

Nos dois casos a VRAM voltou ao baseline observado após unload

## Memória

Pico observado do processo llama-server

```text
4947095552 bytes
≈ 4.61 GiB
```

RSS do runner Python ao final

```text
91963392 bytes
≈ 87.7 MiB
```

Máximo delta de VRAM

```text
4215 MiB
```

## Tamanho do índice temporário real

```text
SQLite      = 11808768 bytes
Qdrant      = 78791713 bytes
total       = 90600481 bytes
```

Total aproximado

`86.4 MiB`

## Processo antigo encontrado

Antes do benchmark existia um llama-server antigo

```text
PID 2732
porta 19109
```

Uma chamada real confirmou que era Jina Code 1536D

O Remote Desktop não conseguiu encerrá-lo por acesso negado

O próprio CodeBridge executou

`taskkill /PID 2732 /F`

Resultado

`ÊXITO`

Depois disso os probes reais de Text e Code foram executados com load → embedding → unload antes do benchmark completo

## Probes reais antes do benchmark

Text

```text
load ≈ 4.862 s
dimension = 1024
norm ≈ 0.999999996
unload ≈ 109 ms
```

Code

```text
load ≈ 3.223 s
dimension = 1536
norm ≈ 1.000000031
unload ≈ 221 ms
```

## Infraestrutura adicionada

`rag/benchmark/metrics.py`

- Recall@5
- Recall@10
- MRR
- latência
- RSS
- VRAM
- tamanho de índice
- RSS por PID no Windows sem dependência psutil

`rag/benchmark/corpus.py`

- corpus usando políticas reais
- chunkers reais
- IDs determinísticos
- SQLite real
- FTS5 real

`benchmarks/run_rag014_semantic_benchmark.py`

- indexação text real
- indexação code real
- Qdrant Local
- embeddings de queries
- routing
- RRF
- dedup
- métricas
- recursos

## Resultado do critério RAG-014-C

As métricas exigidas pelo handoff foram medidas

- Recall@5 ✅
- Recall@10 ✅
- MRR ✅
- cold latency ✅
- warm latency ✅
- RAM ✅
- VRAM ✅
- tamanho do índice ✅

O fato de as métricas de qualidade estarem abaixo do threshold não invalida a medição

Essa decisão pertence ao RAG-014-D

## Próximo passo

`RAG-014-D — Critério mínimo e gate de go-live`

O benchmark será comparado aos thresholds congelados

O sistema não será liberado para produção apenas porque executou sem erro
