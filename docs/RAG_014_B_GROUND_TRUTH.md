# RAG-014-B — Ground truth manual

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-014-benchmark`

## Objetivo

Registrar manualmente as fontes esperadas para as 100 consultas do dataset RAG-014-A

Requisito do handoff

`Registrar manualmente fontes esperadas`

## Arquivo

`benchmarks/rag014_ground_truth.jsonl`

Cada linha contém

```text
id
expected_paths
acceptance
annotation_status
```

## Cobertura

O ground truth cobre exatamente

`rag014-001`

até

`rag014-100`

sem IDs ausentes

A ordem acompanha exatamente o dataset de consultas

## Regra de aceitação

Política congelada inicial

`ANY_EXPECTED_PATH_IN_TOP_K`

Uma consulta é considerada recuperada quando ao menos um dos paths anotados manualmente aparece entre os resultados relevantes avaliados no top-k da métrica

Algumas perguntas possuem mais de uma fonte válida porque o comportamento pode estar documentado e implementado em arquivos complementares

Exemplos

- runtime + bridge MCP
- documentação + implementação
- source policy + execution inventory
- staleness + estado Git

## Fontes reais

Todas as fontes anotadas foram verificadas contra o repositório atual

Resultado da auditoria

```text
ROWS 100
MISSING []
```

Nenhum path inexistente foi aceito no ground truth

## Natureza da anotação

`annotation_status=MANUAL_RAG_014_B`

A anotação foi feita consulta por consulta com base no objetivo semântico de cada pergunta

Não foi gerada automaticamente a partir de ranking

Isso evita transformar a saída do próprio sistema avaliado em ground truth

## Exemplos

Pergunta sobre classificador de consulta

Fonte esperada

`rag/runtime/query_classifier.py`

Pergunta sobre RRF

Fonte esperada

`rag/ranking/rrf.py`

Pergunta sobre integração MCP real

Fonte esperada

`docs/RAG_013_MCP_INTEGRATION.md`

Pergunta sobre logs de restart

Fonte esperada

`phase4_restart.log`

Pergunta PT-BR sobre fallback FTS5

Fonte esperada

`rag/runtime/search_service.py`

## Validação automática

Criado

`tests/test_rag_014_ground_truth.py`

O teste garante

- 100 anotações
- IDs idênticos ao dataset
- pelo menos uma fonte por consulta
- todos os paths existem
- IDs são únicos
- policy uniforme
- annotation_status manual
- schema estável

## Fronteiras

RAG-014-B não calcula métricas

Isso pertence ao RAG-014-C

RAG-014-B não define threshold de go-live

Isso pertence ao RAG-014-D

## Critério de aceitação

RAG-014-B está concluído quando

- todas as 100 consultas têm ground truth
- todas as fontes anotadas existem
- anotações não dependem da saída do retriever
- policy de aceitação está congelada
- teste automático passa
- git diff check passa

## Próximo passo

`RAG-014-C — Métricas`

Medir

- Recall@5
- Recall@10
- MRR
- latência cold
- latência warm
- RAM
- VRAM
- tamanho do índice
