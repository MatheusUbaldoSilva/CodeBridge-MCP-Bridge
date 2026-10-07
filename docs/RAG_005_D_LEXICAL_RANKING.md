# RAG-005-D — Ranking lexical

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-005-sqlite-fts`

## Objetivo

Congelar score e rank lexical mínimos utilizáveis para fechar o RAG-005

Nenhum embedding entra neste marco

## Motor

O ranking usa exclusivamente

`FTS5 bm25`

sobre a projeção `rag_chunks_fts`

## Pesos congelados

A ordem das colunas FTS é

1 chunk_id
2 document_id
3 project_id
4 content
5 path
6 symbol
7 git_message
8 title
9 heading_path

Pesos

```text
chunk_id      0.0
document_id   0.0
project_id    0.0
content       1.0
path          3.0
symbol        6.0
git_message   2.0
title         4.0
heading_path  3.0
```

Os três campos de identidade são UNINDEXED e recebem peso zero

Prioridade mínima pretendida

`symbol > title > path/heading > git_message > content`

## Score público

FTS5 BM25 usa valor menor como melhor distância

O contrato público do CodeBridge usa maior como melhor score

Por isso

```text
score = -bm25
```

Nenhuma normalização adicional é aplicada no RAG-005

Isso evita inventar uma escala falsa antes do retrieval híbrido futuro

## Rank

`rank` é a posição final 1-based depois da ordenação

Ordem

1 BM25 crescente
2 document_id crescente
3 ordinal crescente
4 chunk_id crescente

Empates de score portanto permanecem determinísticos

## Contrato retornado

`search_lexical_ranked` retorna diretamente o contrato estável

`SearchResult`

do RAG-001-C

Campos importantes

- chunk_id
- document_id
- content
- metadata
- score
- rank
- retrieval_modes
- stale

`retrieval_modes`

recebe

`LEXICAL_FTS5_BM25`

`stale`

permanece `False` nesta camada

## Segurança e filtros

A política de query segura do RAG-005-C é reutilizada

Continuam valendo

- frase FTS literal
- project_id obrigatório
- source_types
- path_filter literal
- branch exata
- top_k

Nenhuma expressão FTS crua é habilitada pelo ranking

## Provas

O corpus prova que

- symbol vence title
- title vence content
- path e heading possuem o mesmo peso
- empate usa tiebreak determinístico
- rank começa em 1
- SearchResult é usado
- filtros continuam valendo
- GetMoveSpeedProvenance recebe score/rank
- codebridge_wait recebe score/rank
- EXECUTION_V2_WAIT recebe score/rank
- execução repetida é determinística

## Ausências intencionais

RAG-005-D não usa

- embedding
- vetor
- cosine
- Jina
- reranker
- score híbrido

Esses elementos pertencem aos marcos posteriores

## Implementação

Criado

`rag/index/lexical_ranking.py`

API pública

- LEXICAL_RETRIEVAL_MODE
- LEXICAL_BM25_WEIGHTS
- lexical_score_from_bm25
- search_lexical_ranked

Atualizado

`rag/index/__init__.py`

## Critério de aceitação

RAG-005-D está concluído quando

- BM25 é a única relevância
- pesos ficam congelados
- score é finito e maior é melhor
- rank é 1-based
- empate é determinístico
- filtros do RAG-005-C continuam funcionando
- as três consultas do handoff recebem score e rank
- suíte RAG passa
- diff check passa
- nenhum embedding existe

Com o RAG-005-D validado o RAG-005 pode ser fechado formalmente
