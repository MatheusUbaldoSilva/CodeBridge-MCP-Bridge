# RAG-013-E — Contratos públicos de erro RAG

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Consolidar erros estáveis para as tools MCP RAG

Requisitos do handoff

- model load
- index unavailable
- source missing
- stale result
- invalid scope

## Tipos públicos

Criado

`RagPublicErrorType`

com

```text
MODEL_LOAD
INDEX_UNAVAILABLE
SOURCE_MISSING
STALE_RESULT
INVALID_SCOPE
EXECUTOR_UNAVAILABLE
INTERNAL_ERROR
```

Os cinco primeiros cobrem diretamente o handoff

`EXECUTOR_UNAVAILABLE` deixa explícito quando uma operação pesada foi solicitada mas o executor de produção ainda não está registrado

`INTERNAL_ERROR` impede vazar tipos internos desconhecidos como contrato público

## Payload

`RagPublicError`

contém

```text
error_type
error_message
retryable
```

As tools MCP também mantêm

```text
operation_ok
operation_error_type
operation_error_message
```

usando o mesmo tipo público

## MODEL_LOAD

Exemplos internos mapeados

- ModelLoadError
- falha de fallback de modelo
- estado/protocolo de embedding

Contrato público

```text
error_type=MODEL_LOAD
retryable=true
```

## INDEX_UNAVAILABLE

Inclui

- índice SQLite ausente
- contexto sem índice
- schema/FTS indisponível
- backend vetorial indisponível

Contrato

```text
error_type=INDEX_UNAVAILABLE
retryable=true
```

## SOURCE_MISSING

Chunk ou fonte selecionada não existe no projeto autorizado

```text
error_type=SOURCE_MISSING
retryable=false
```

## STALE_RESULT

Criado

`RagStaleResultError`

`codebridge_get_context` passou a aceitar opcionalmente

```text
project_root
allow_stale=false
```

Quando project_root é fornecido e o chunk possui path + SHA

```text
SHA indexado
+
arquivo atual
↓
evaluate_source_staleness
↓
STALE
↓
RagStaleResultError
↓
error_type=STALE_RESULT
```

Com `allow_stale=true` o chamador pode optar explicitamente por aceitar o conteúdo histórico

## INVALID_SCOPE

Entradas fora do contrato ou seleção não autorizada retornam

`INVALID_SCOPE`

Exemplos

- lista vazia de chunks
- IDs duplicados
- mais de 100 chunks
- path não autorizado
- source type inválido

## Bridge

`author_mcp/rag_bridge.py`

expõe

`format_rag_error()`

O servidor MCP crítico não importa o pacote RAG diretamente

A classificação acontece somente quando uma tool RAG falha

Se até a classificação falhar existe fallback local para erro interno sem derrubar o MCP

## Tools atualizadas

- codebridge_rag_status
- codebridge_rag_index
- codebridge_search_context
- codebridge_get_context

Todas usam o contrato público de erro

## Provas

Testes unitários validam mapeamento de

- model load
- index unavailable
- source missing
- stale result
- invalid scope
- executor unavailable
- internal error

Testes MCP reais validam

- index executor ausente → EXECUTOR_UNAVAILABLE
- índice de busca ausente → INDEX_UNAVAILABLE
- seleção cross-project → SOURCE_MISSING
- resultado com SHA divergente → STALE_RESULT
- seleção inválida → INVALID_SCOPE

## Teste stale real

O teste MCP

1 cria índice com SHA antigo
2 cria arquivo atual com conteúdo diferente
3 chama codebridge_get_context com project_root
4 recebe

```text
operation_ok=false
error_type=STALE_RESULT
retryable=false
```

## Arquivos

Criado

`rag/runtime/errors.py`

Atualizado

`rag/runtime/__init__.py`

Atualizado

`rag/runtime/context_service.py`

Atualizado

`author_mcp/rag_bridge.py`

Atualizado

`author_mcp/mcp_server.py`

Criado

`tests/test_rag_public_errors.py`

Atualizados testes MCP das fases B C D

Criado

`docs/RAG_013_E_ERROR_CONTRACTS.md`

## Testes específicos consolidados

```text
Ran 17 tests
OK
```

## Estado após RAG-013-E

As quatro tools previstas no handoff existem

```text
codebridge_rag_status
codebridge_rag_index
codebridge_search_context
codebridge_get_context
```

Os contratos de erro também existem

O fechamento completo do RAG-013 ainda exige integração real dos executores pesados de indexação e busca semântica no processo de produção

Isso não será marcado como concluído até essa integração ser provada
