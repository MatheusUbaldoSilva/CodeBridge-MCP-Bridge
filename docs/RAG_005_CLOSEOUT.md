# Fechamento — RAG-005 — SQLite + FTS5 lexical

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-005-sqlite-fts`

## Status

RAG-005-A ✅

RAG-005-B ✅

RAG-005-C ✅

RAG-005-D ✅

Resultado

**RAG-005 FECHADO**

## Objetivo do marco

Construir o índice textual local do CodeBridge sem embeddings

O marco precisava

- SQLite dedicado ao RAG
- FTS5
- busca lexical segura
- ranking lexical mínimo utilizável
- score e rank estáveis
- zero dependência de embedding

## RAG-005-A — Schema SQLite

Commit principal

`978ec347fd74ca105524c98da02c769e3ff2b6c9`

Implementado em

`rag/index/sqlite_schema.py`

Schema relacional v1

- rag_documents
- rag_chunks
- rag_chunk_symbols
- rag_index_state

`PRAGMA user_version = 1`

Foreign keys constraints e índices B-tree foram validados

Nenhum FTS5 foi antecipado no schema base

Nenhum embedding foi criado

### Ajuste de teste herdado

Commit

`4ad0050ee0a61f2417a612f985dd31078974f008`

A suíte completa revelou que o teste antigo usava `cache/data.bin` para provar extensão binária

A política corretamente classificava esse path como CACHE devido à precedência do diretório negado

O teste foi corrigido para `artifacts/data.bin`

A denylist não foi alterada

## RAG-005-B — FTS5

Commit

`efa4eec6b59776b241b2a8dfe0adfb124744e011`

Implementado em

`rag/index/fts5.py`

Projeção virtual

`rag_chunks_fts`

Campos indexados

- content
- path
- symbol
- git_message
- title
- heading_path

Metadados não full-text

- chunk_id
- document_id
- project_id

A projeção é reconstruível e não substitui as tabelas relacionais

Triggers mantêm FTS sincronizado com chunks e símbolos

`rebuild_fts5` recompõe a projeção a partir da fonte relacional

## RAG-005-C — Busca lexical

Commit final limpo

`e8df4b2cc5bbe0b0a7750c5e95df63d4d2cc920e`

Implementado em

`rag/index/lexical_search.py`

A consulta é tratada como frase literal FTS parametrizada

Filtros

- project_id obrigatório
- source_types
- path_filter literal
- branch exata
- top_k

Provas do handoff

`GetMoveSpeedProvenance` ✅

`codebridge_wait` ✅

`EXECUTION_V2_WAIT` ✅

O RAG-005-C deliberadamente não publica score ou rank

## RAG-005-D — Ranking lexical

Commit final limpo

`10e830858881605971fed5f27b97c1bf0520821c`

Implementado em

`rag/index/lexical_ranking.py`

Motor de relevância

`FTS5 bm25`

Pesos congelados na ordem das colunas FTS

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

Prioridade mínima

`symbol > title > path/heading > git_message > content`

Score público

```text
score = -bm25
```

Portanto score maior representa resultado melhor

Rank

- 1-based
- ordenado primeiro por BM25
- desempate por document_id
- depois ordinal
- depois chunk_id

O retorno usa o contrato estável

`SearchResult`

com

`retrieval_modes = ("LEXICAL_FTS5_BM25",)`

## Correção durante auditoria do RAG-005-D

O primeiro corpus assumia incorretamente que campos com o mesmo peso BM25 necessariamente teriam o mesmo score

A execução real mostrou que estatísticas de comprimento de coluna também afetam BM25

A política de ranking estava correta

O teste foi corrigido para verificar separadamente

- igualdade dos pesos congelados de path e heading_path
- tiebreak determinístico em candidatos que realmente possuem score BM25 igual

A branch foi regravada antes do fechamento

O commit oficial do RAG-005-D é somente

`10e830858881605971fed5f27b97c1bf0520821c`

## Validação real no Windows

Validação executada no computador autorizado usando CodeBridge

Rota funcional

```text
codebridge_prepare
→
codebridge_execute_prepared
```

Foi usado worktree temporário isolado

`%TEMP%\codebridge-rag005d-validation`

HEAD final validado

`10e8308 feat(rag-005-d): freeze lexical BM25 ranking`

### Ranking específico

Resultado

```text
Ran 13 tests
OK
```

Coberturas incluem

- pesos congelados
- score = -bm25
- valores não finitos rejeitados
- symbol acima de title e content
- pesos iguais de path e heading
- empate BM25 com desempate estável
- rank 1-based
- SearchResult
- project scope
- filtros
- três consultas do handoff
- determinismo
- ausência de embedding e híbrido

### Suíte RAG completa

Comando

```text
python -m unittest discover -s tests -p 'test_rag_*.py' -v
```

Resultado real

```text
Ran 242 tests
OK
exit_code = 0
```

## Git diff check

Executado para o RAG-005-D

```text
git diff --check e8df4b2cc5bbe0b0a7750c5e95df63d4d2cc920e..HEAD
```

Resultado

```text
exit_code = 0
```

## Worktree e checkout principal

Antes da remoção

```text
## HEAD (no branch)
```

sem alterações locais

Depois

- worktree temporário removido
- git worktree prune executado
- checkout principal permaneceu em main
- status principal sem modificações locais

Status observado

```text
## main...origin/main
```

## Auditoria Git do RAG-005-D

Comparação

`e8df4b2..10e8308`

Resultado

- 1 commit à frente
- 0 atrás
- exatamente 4 arquivos alterados

Arquivos

- docs/RAG_005_D_LEXICAL_RANKING.md
- rag/index/__init__.py
- rag/index/lexical_ranking.py
- tests/test_rag_lexical_ranking.py

## Commits preservados do RAG-005

```text
978ec34  feat(rag-005-a): add SQLite text index schema
4ad0050  test(rag): isolate binary denylist case
efa4eec  feat(rag-005-b): add synchronized FTS5 projection
e8df4b2  feat(rag-005-c): add safe lexical search
10e8308  feat(rag-005-d): freeze lexical BM25 ranking
```

## Invariantes confirmados

1. SQLite dedicado possui schema relacional versionado
2. import não cria banco automaticamente
3. FTS5 é projeção reconstruível
4. persistência relacional continua fonte do índice textual
5. content path symbol git_message title e heading_path entram no FTS
6. projeto é isolado por project_id
7. query lexical não recebe sintaxe FTS crua
8. as três consultas obrigatórias foram provadas
9. BM25 é a única relevância do RAG-005
10. pesos de campos estão congelados
11. score maior representa resultado melhor
12. rank é 1-based e determinístico
13. SearchResult é usado no ranking
14. 242 testes RAG passaram no Windows
15. diff check passou
16. worktree temporário foi removido
17. checkout principal permaneceu limpo
18. nenhum embedding foi criado
19. nenhum vetor foi criado
20. nenhum modelo Jina foi carregado
21. executor MCP não foi alterado pelo RAG

## Fronteira para o próximo marco

O RAG-005 termina propositalmente como retrieval lexical puro

O próximo marco é

`RAG-006 — Jina v5 Text Small`

RAG-006-A começa avaliando backend de inferência compatível com

- GPU quando disponível
- CPU fallback
- Windows
- distribuição com CodeBridge

Nenhum modelo deve ser baixado silenciosamente
