# RAG-013-A — Tool MCP codebridge_rag_status

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Expor por MCP um snapshot somente leitura do estado atual do RAG

Requisito do handoff

- índice
- projetos
- modelos
- loaded/unloaded
- backend
- CPU/GPU
- última indexação

## Tool

Nome público

`codebridge_rag_status`

A tool é registrada com

```text
read_only_hint=True
idempotent_hint=True
open_world_hint=False
structured_output=True
```

## Isolamento do MCP crítico

O servidor MCP crítico continua sem importar `rag` diretamente

Foi criado

`author_mcp/rag_bridge.py`

A ponte importa o pacote RAG somente quando `codebridge_rag_status` é chamado

Consequência

falha completa do pacote RAG não impede import das tools críticas de execução

Isso preserva a regra já fechada de isolamento

## Índice

A resposta expõe

```text
state
manifest_path
manifest_exists
manifest_entries
sqlite_path
sqlite_exists
qdrant_path
qdrant_exists
```

Estados agregados possíveis

```text
EMPTY
READY
STALE
INDEXING
ERROR
```

A leitura do SQLite é aberta em modo read-only

Consultar status não cria banco nem manifest

## Projetos

Projetos são consolidados a partir do manifest incremental e do estado SQLite

Por projeto podem aparecer

- manifest_entries
- text_entries
- code_entries
- text_model_versions
- code_model_versions
- index_state
- source_revision
- last_indexed_at
- document_count
- chunk_count
- last_error_type
- last_error_message

Somente campos disponíveis no estado local são retornados

## Modelos

Text

`jinaai/jina-embeddings-v5-text-small`

Code

`jinaai/jina-code-embeddings-1.5b`

Para cada modelo a resposta informa

- revision
- artifact_path
- installed
- loaded
- runtime_state
- execution_mode
- gpu_preferred
- cpu_fallback_required

## Loaded e CPU/GPU

A inspeção de runtime procura processos `llama-server` pelo arquivo de modelo

Estados

```text
runtime_state
LOADED
UNLOADED
UNKNOWN
```

Modo

```text
CPU
GPU
UNLOADED
UNKNOWN
```

Para permitir inspeção real de processos no ambiente MCP foi adicionado

`psutil>=7,<8`

ao `author_mcp/requirements.txt`

## Backend

Resposta atual

```text
vector=QDRANT_LOCAL
package=qdrant-client
package_version=1.19.1
mode=PERSISTED_LOCAL
external_server_required=false
```

## Última indexação

`last_indexed_at`

é obtido do maior timestamp registrado em `rag_index_state`

Quando ainda não houve indexação

`null`

## Estado real observado durante integração

No ambiente atual a chamada direta pelo Python do MCP retornou

```text
index.state=EMPTY
text.runtime_state=UNLOADED
code.runtime_state=LOADED
code.execution_mode=CPU
backend.vector=QDRANT_LOCAL
last_indexed_at=null
```

Isso também confirmou que o status consegue distinguir residência real de modelo

## Falha do RAG

Se a ponte RAG falhar a tool retorna contrato estruturado

```text
operation_ok=false
available=false
error_type
error_message
```

Sem derrubar as demais tools MCP

## Testes

`tests/test_rag_status_snapshot.py`

valida

- estado vazio sem criar índice
- projetos e versões vindos do manifest
- última indexação vinda do SQLite
- promoção de estado ERROR

`tests/test_rag_mcp_status_tool.py`

usa o Python real de

`author_mcp/.venv`

e valida

- registro público da tool
- resposta MCP estruturada
- campos exigidos pelo handoff
- loaded/unloaded
- CPU/GPU
- backend
- ausência de criação silenciosa do índice

## Arquivos

Criado

`rag/runtime/status.py`

Atualizado

`rag/runtime/__init__.py`

Criado

`author_mcp/rag_bridge.py`

Atualizado

`author_mcp/mcp_server.py`

Atualizado

`author_mcp/requirements.txt`

Criado

`tests/test_rag_status_snapshot.py`

Criado

`tests/test_rag_mcp_status_tool.py`

Criado

`docs/RAG_013_A_RAG_STATUS.md`

## Validação

Suíte RAG após a integração

```text
Ran 574 tests
OK
```

`git diff --check`

OK

## Fronteiras

RAG-013-A não inicia indexação

RAG-013-A não executa busca

RAG-013-A não carrega modelo por conta própria

RAG-013-A não cria índice ao consultar status

Esses comportamentos pertencem às próximas tools do RAG-013
