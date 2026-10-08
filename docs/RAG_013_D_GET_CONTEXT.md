# RAG-013-D — Tool MCP codebridge_get_context

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Recuperar conteúdo completo e autorizado de resultados RAG selecionados

## Tool

`codebridge_get_context`

Entradas

```text
project
chunk_ids
include_document_content=false
```

A tool é somente leitura e nunca aceita path arbitrário como chave de leitura

A seleção ocorre por `chunk_id` já retornado pelo RAG e é sempre limitada ao projeto informado

## Autorização

A consulta exige simultaneamente

```text
chunk_id selecionado
project_id do chunk == project solicitado
project_id do documento == project solicitado
```

Um chunk de outro projeto é tratado como indisponível

A path armazenada também é revalidada pela denylist central antes da entrega

## Conteúdo

Por padrão retorna o conteúdo completo do chunk persistido

Com

`include_document_content=true`

também retorna o conteúdo completo do documento pai autorizado pelo mesmo projeto

## Limites

A seleção

- precisa conter pelo menos um chunk
- não aceita IDs duplicados
- aceita no máximo 100 chunks por chamada

## Índice

SQLite é aberto em modo read-only

Índice ausente gera erro estruturado

Nenhum banco é criado automaticamente

## Erros

`RagContextSourceMissingError`

chunk inexistente ou fora do projeto

`RagContextInvalidScopeError`

seleção inválida ou path não autorizada

`RagContextIndexUnavailableError`

índice indisponível

## Integração MCP real

Os testes usam o Python real de `author_mcp/.venv` e validam

- registro de codebridge_get_context
- leitura real de chunk
- leitura opcional do documento completo
- bloqueio cross-project
- erro estruturado

## Arquivos

Criado

`rag/runtime/context_service.py`

Atualizado

`rag/runtime/__init__.py`

Atualizado

`author_mcp/rag_bridge.py`

Atualizado

`author_mcp/mcp_server.py`

Criado

`tests/test_rag_context_service.py`

Criado

`tests/test_rag_mcp_get_context.py`

Criado

`docs/RAG_013_D_GET_CONTEXT.md`

## Testes específicos

```text
Ran 7 tests
OK
```

## Fronteira

A consolidação dos contratos de erro públicos ocorre no RAG-013-E
