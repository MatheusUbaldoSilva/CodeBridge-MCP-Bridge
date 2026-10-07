# RAG-010-B — FTS5 + vetor de código

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Combinar candidatos FTS5 com candidatos vetoriais da coleção `code`

Requisito do handoff

`FTS5 + vetor de código — Combinar resultados`

Assim como no RAG-010-A a fusão final ainda pertence ao RAG-010-D e a deduplicação ao RAG-010-E

## Recuperação lexical

Permanece

`search_lexical_ranked()`

Modo

`LEXICAL_FTS5_BM25`

Nenhuma política BM25 foi alterada

## Recuperação vetorial de código

Criado

`search_code_vector()`

Coleção

`code`

Dimensão

`1536`

Distância

`Cosine`

Modo

`VECTOR_CODE_COSINE`

A query vector é fornecida pelo chamador já no contrato do Jina Code fechado em RAG-007

## Filtros

Mantidos de forma equivalente ao caminho textual

- project namespace obrigatório
- source_types quando fornecidos
- branch quando fornecida
- path_filter com semântica de substring

## Candidatos combinados

Criado

`CodeHybridCandidates`

com

```text
lexical
vector
```

Criado

`collect_code_hybrid_candidates()`

Os dois rankings permanecem separados nesta fase

Não existe soma de scores

Não existe RRF ainda

Não existe deduplicação ainda

## Provas

A suíte específica valida

- retorno vetorial de código como SearchResult
- retrieval mode VECTOR_CODE_COSINE
- isolamento por namespace
- path filter
- coexistência dos candidatos FTS5 e vetoriais
- rejeição de query vector com dimensão inválida

## Arquivos

Criado

`rag/retrieval/hybrid_code.py`

Atualizado

`rag/retrieval/__init__.py`

Criado

`tests/test_rag_hybrid_code.py`

Criado

`docs/RAG_010_B_CODE_HYBRID.md`

## Fronteiras

RAG-010-B não implementa

- consulta HYBRID que usa text e code na mesma solicitação
- Reciprocal Rank Fusion
- deduplicação

Esses pontos ficam para RAG-010-C D E

## Critério de aceitação

RAG-010-B está concluído quando

- FTS5 e vetor code produzem candidatos simultaneamente
- coleção code usa 1536D
- namespace é respeitado
- filtros básicos permanecem compatíveis
- rankings continuam separados
- testes específicos passam
- suíte RAG passa
- git diff check passa
