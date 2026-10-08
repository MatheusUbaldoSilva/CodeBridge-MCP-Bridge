# RAG-013-C — Tool MCP codebridge_search_context

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Expor busca de contexto pelo MCP com as entradas exigidas pelo handoff

```text
query
project
source_types
top_k
path_filter
branch
```

## Tool

`codebridge_search_context`

A tool é somente leitura

```text
read_only_hint=True
idempotent_hint=True
open_world_hint=False
structured_output=True
```

## Rotas

A consulta reutiliza o classificador determinístico do RAG-008

```text
TEXT
CODE
HYBRID
LEXICAL_ONLY
```

A resposta expõe separadamente

`requested_route`

e

`effective_route`

## Fallback honesto

O executor semântico pesado é registrável no bridge por

`register_rag_search_executor()`

Quando ele está disponível a rota solicitada é executada por esse backend

Quando não está disponível a tool não inventa resultado vetorial

Ela executa FTS5 real e informa

```text
effective_route=LEXICAL_ONLY
fallback_reason=SEMANTIC_EXECUTOR_UNAVAILABLE
```

Assim a busca continua útil sem esconder que houve fallback

## Índice lexical

A conexão SQLite é aberta em modo read-only

Se o índice não existe a resposta MCP é erro estruturado

`RagSearchIndexUnavailableError`

A busca não cria índice automaticamente

## Filtros

O contrato `SearchQuery` existente é reutilizado para

- source_types
- top_k
- path_filter
- branch
- project_id

Source types inválidos são rejeitados

top_k menor que 1 é rejeitado

## Resultado

Cada resultado preserva

- chunk_id
- document_id
- content
- metadata
- score
- rank
- retrieval_modes
- stale

Metadata inclui os campos Git já fechados no RAG-011

## Integração MCP real

Os testes usam o Python real de

`author_mcp/.venv`

e validam

- registro de codebridge_search_context
- busca FTS5 real
- filtros
- fallback explícito
- índice ausente como erro estruturado
- executor semântico registrado sendo usado

## Estado de integração

A superfície e o fallback real estão fechados

O executor semântico pesado de produção ainda precisa ser registrado antes do closeout completo do RAG-013

Nenhuma resposta vetorial é simulada

## Arquivos

Criado

`rag/runtime/search_service.py`

Atualizado

`rag/runtime/__init__.py`

Atualizado

`author_mcp/rag_bridge.py`

Atualizado

`author_mcp/mcp_server.py`

Criado

`tests/test_rag_search_service.py`

Criado

`tests/test_rag_mcp_search_context.py`

Criado

`docs/RAG_013_C_SEARCH_CONTEXT.md`

## Testes específicos

```text
Ran 9 tests
OK
```

## Fronteiras

RAG-013-C não recupera conteúdo completo fora do resultado selecionado

Isso pertence ao RAG-013-D

Contratos de erro comuns serão consolidados no RAG-013-E
