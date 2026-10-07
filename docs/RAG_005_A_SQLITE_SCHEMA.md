# RAG-005-A — Schema do índice textual SQLite

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-005-sqlite-fts`

## Objetivo

Criar o SQLite dedicado à camada RAG

Este subpasso congela somente o schema relacional textual

FTS5 pertence ao RAG-005-B

Busca lexical pertence ao RAG-005-C

Ranking pertence ao RAG-005-D

Embeddings continuam fora do RAG-005 inteiro

## Arquivo de banco

Nome padrão exposto pelo módulo

`rag_index.sqlite3`

Nenhum arquivo SQLite é criado durante import

Nenhum banco é versionado no Git

A criação só acontece por chamada explícita a

`connect_rag_index`

ou

`initialize_rag_schema`

## Versão

Primeira versão

`SCHEMA_VERSION = 1`

Persistida via

`PRAGMA user_version = 1`

Comportamento

- versão 0 inicializa schema v1
- versão 1 valida integridade
- versão desconhecida é recusada
- schema v1 incompleto é recusado

Não existe migração silenciosa nesta fase

## Tabelas

### rag_documents

Representa a fonte textual persistida

Campos principais

- document_id
- project_id
- source_type
- content
- path
- symbol
- line_start
- line_end
- git_branch
- git_commit
- sha256
- indexed_at
- source_id
- title
- heading_path
- git_message

### rag_chunks

Representa as unidades recuperáveis produzidas pelos chunkers

Campos principais

- chunk_id
- document_id
- project_id
- ordinal
- parent_chunk_id
- content
- source_type
- proveniência
- title
- heading_path
- git_message
- chunk_kind
- parser_mode

Há unicidade de

`document_id + ordinal`

Chunks pertencem a documentos por foreign key

Excluir um documento remove seus chunks

### rag_chunk_symbols

Permite associar múltiplos símbolos ao mesmo chunk

Campos

- chunk_id
- symbol_kind
- name
- qualified_name
- parent
- line_start
- line_end

Não foi criado symbol_id definitivo

Essa decisão continua reservada à política de IDs determinísticos do RAG-009-D

Excluir um chunk remove suas associações de símbolos

### rag_index_state

Estado textual do índice por projeto

Campos

- project_id
- state
- schema_version
- source_revision
- last_indexed_at
- document_count
- chunk_count
- last_error_type
- last_error_message

Estados aceitos seguem o contrato RAG-001-C

- UNAVAILABLE
- EMPTY
- INDEXING
- READY
- STALE
- ERROR

## Campos preparados para RAG-005-B

O schema normal já preserva os campos que o FTS5 precisará indexar depois

- content
- path
- symbol
- git_message
- title
- heading_path

Isso não cria FTS antecipadamente

## Índices B-tree normais

Criados índices relacionais para

- project_id + source_type
- project_id + path
- document_id + ordinal
- git_commit
- symbol name
- qualified_name

Esses índices não são FTS

## Foreign keys

`connect_rag_index` habilita

`PRAGMA foreign_keys = ON`

Cascades testados

`document → chunks → chunk_symbols`

## Integridade

O schema rejeita

- project_id vazio
- IDs vazios
- source_type inválido
- ordinal negativo
- line_start menor que 1
- line_end anterior a line_start
- parser_mode desconhecido
- symbol_kind desconhecido
- estado de índice desconhecido
- SHA256 com tamanho diferente de 64 quando presente

## Ausências intencionais

RAG-005-A não possui

- CREATE VIRTUAL TABLE
- FTS5
- MATCH
- BM25
- ranking lexical
- embedding
- vector
- modelo Jina

Os testes inspecionam `sqlite_master` para provar essas ausências

## Implementação

Criado

`rag/index/sqlite_schema.py`

API pública

- SCHEMA_VERSION
- DEFAULT_DATABASE_FILENAME
- REQUIRED_TABLES
- RagSchemaVersionError
- RagSchemaIntegrityError
- initialize_rag_schema
- connect_rag_index
- schema_table_names

Criado também

`rag/index/__init__.py`

## Testes

Criado

`tests/test_rag_sqlite_schema.py`

Cobertura

- schema em memória
- banco físico temporário
- ausência de efeito colateral no import
- foreign keys
- cascade
- unicidade de ordinal
- line constraints
- source_type
- parser_mode
- ausência de FTS
- ausência de embedding
- campos futuros do FTS
- estados do índice
- idempotência
- versão desconhecida
- schema incompleto
- índices B-tree

## Efeitos colaterais

Import de `rag.index` não abre banco

Import não cria arquivo

Import não inicia indexação

Import não executa shell

Import não carrega modelo

O SQLite só é aberto por chamada explícita

## Critério de aceitação

RAG-005-A está concluído quando

- SQLite dedicado possui schema v1
- documentos chunks símbolos e estado possuem tabelas
- foreign keys e constraints funcionam
- schema é idempotente
- versão incompatível falha com segurança
- nenhum FTS5 existe
- nenhum embedding existe
- teste em banco físico temporário passa
- diff check passa
