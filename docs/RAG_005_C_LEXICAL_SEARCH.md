# RAG-005-C — Busca lexical

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-005-sqlite-fts`

## Objetivo

Transformar a projeção FTS5 do RAG-005-B em uma API pública de busca lexical

O handoff exige provar consultas como

- GetMoveSpeedProvenance
- codebridge_wait
- EXECUTION_V2_WAIT

Ranking lexical continua reservado ao RAG-005-D

## Consulta segura

O texto de entrada não é enviado ao FTS5 como expressão crua

Ele é convertido em frase literal FTS

Exemplo conceitual

`codebridge_wait`

vira uma frase FTS escapada e parametrizada

Operadores escritos pelo usuário como

- OR
- AND
- NOT
- parênteses
- aspas

não recebem autoridade para alterar a estrutura SQL ou a política da busca

A consulta precisa conter ao menos um token lexical

Pontuação isolada é rejeitada

## Sem ranking nesta fase

RAG-005-C não define relevância

O retorno é ordenado somente para determinismo por

- document_id
- ordinal
- chunk_id

Isso não é tratado como score de relevância

O contrato `LexicalSearchHit` não possui

- score
- rank

RAG-005-D será responsável por congelar esses campos

## Escopo por projeto

`SearchQuery.project_id` é obrigatório pelo contrato RAG-001

A busca aplica comparação exata em `rag_chunks.project_id`

Isso impede resultado lexical de outro projeto mesmo que o FTS encontre o mesmo termo

## Filtro de source_type

Quando `SearchQuery.source_types` é informado

o filtro é aplicado na tabela relacional `rag_chunks`

Não é interpolado dentro da expressão FTS

## Filtro de path

`path_filter` usa substring literal normalizada para barra POSIX

Caracteres SQL wildcard

- %
- _

são escapados

Portanto não ganham semântica de wildcard do SQL

## Filtro de branch

`SearchQuery.branch` usa igualdade exata em `git_branch`

Valor vazio é rejeitado

## Retorno

`LexicalSearchHit` preserva

- chunk_id
- document_id
- content
- ordinal
- SourceMetadata
- title
- heading_path
- git_message
- chunk_kind
- parser_mode

A fonte persistente continua sendo `rag_chunks`

O FTS localiza candidatos

A linha relacional fornece conteúdo e proveniência retornados

## Provas exigidas pelo handoff

O corpus contém registros separados e prova

`GetMoveSpeedProvenance → chunk-move`

`codebridge_wait → chunk-wait`

`EXECUTION_V2_WAIT → chunk-exec`

Também prova isolamento entre projetos

## FTS explícito

`search_lexical` não cria FTS5

A projeção precisa ter sido inicializada explicitamente por

`initialize_fts5`

Se a projeção estiver ausente ou incompleta a busca falha

Não existe fallback silencioso para LIKE

## Implementação

Criado

`rag/index/lexical_search.py`

API pública

- RagLexicalQueryError
- LexicalSearchHit
- search_lexical

Atualizado

`rag/index/__init__.py`

## Testes

Criado

`tests/test_rag_lexical_search.py`

Cobertura

- GetMoveSpeedProvenance
- codebridge_wait
- EXECUTION_V2_WAIT
- isolamento project_id
- filtro source_type
- path literal
- normalização de path Windows
- branch exata
- operadores FTS tratados como texto
- aspas escapadas
- query sem token rejeitada
- filtros vazios rejeitados
- top_k
- ordem determinística
- preservação de SourceMetadata
- ausência de score e rank
- FTS precisa ser inicializado
- ausência de BM25

## Não antecipado

RAG-005-C não implementa

- BM25
- pesos por campo
- score
- rank
- embedding
- vetor
- Jina

## Critério de aceitação

RAG-005-C está concluído quando

- as três consultas exigidas encontram o chunk correto
- consulta não é interpretada como FTS cru
- project_id impede vazamento
- filtros relacionais funcionam
- metadata retornada vem de rag_chunks
- nenhuma política de relevância foi antecipada
- suíte RAG passa
- diff check passa
