# RAG-010 — Benchmark de retrieval

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Cumprir o critério de fechamento do handoff

`RAG-010 ✅ com benchmark de retrieval`

Este benchmark é um benchmark de integração determinístico do pipeline híbrido

Não substitui o benchmark amplo com perguntas reais planejado para o RAG-014

## Pipeline testado

Cada caso percorre

```text
SearchQuery HYBRID
↓
FTS5 BM25
+
Qdrant text 1024D Cosine
+
Qdrant code 1536D Cosine
↓
Reciprocal Rank Fusion k=60
↓
deduplicação
↓
top 3
```

Foram usados storage reais em memória ou diretório temporário

- SQLite + FTS5 real
- Qdrant Local real

Não foram usados mocks de retrieval

## Dataset

Três casos determinísticos

### Caso 1

Consulta

`cancelamento`

Relevante

`chunk-cancel`

### Caso 2

Consulta

`handoff memoria`

Relevante

`chunk-memory`

### Caso 3

Consulta

`runtime wait`

Relevante

`chunk-wait`

Cada chunk possui vetor-base ortogonal conhecido em

- text 1024D
- code 1536D

Isso permite provar o comportamento da infraestrutura de retrieval e fusão sem introduzir variância de modelo nesta fase

## Métricas

Resultado observado

```text
casos = 3
Hit@1 = 1.000
Recall@3 = 1.000
MRR = 1.000
```

Todos os três chunks relevantes ficaram em primeiro lugar após

- coleta híbrida
- RRF
- deduplicação

## Execução

Comando

```text
python -m unittest tests.test_rag_010_retrieval_benchmark -v
```

Resultado observado

```text
Ran 1 test in 0.698s
OK
```

Esse tempo inclui criação do corpus temporário SQLite/Qdrant e não deve ser tratado como latência de consulta de produção

Benchmark de latência e qualidade com embeddings reais fica reservado para os marcos de benchmark posteriores

## O que este benchmark prova

- FTS5 participa do retrieval
- coleção text participa do retrieval
- coleção code participa do retrieval
- consulta HYBRID alcança os três espaços
- RRF produz ranking final determinístico
- deduplicação pode ser aplicada após a fusão
- o relevante esperado chega ao top 1 nos casos controlados
- todo o pipeline usa os contratos reais das fases RAG-010-A até E

## O que este benchmark não prova

Não mede qualidade geral dos modelos

Não mede recall em corpus real grande

Não mede latência de embedding real

Não mede throughput

Não substitui RAG-014

## Arquivo

Criado

`tests/test_rag_010_retrieval_benchmark.py`

Criado

`docs/RAG_010_RETRIEVAL_BENCHMARK.md`

## Critério

O requisito de benchmark específico para fechamento do RAG-010 está satisfeito

O benchmark amplo e realista permanece explicitamente fora deste marco
