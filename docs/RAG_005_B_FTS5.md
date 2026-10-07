# RAG-005-B — FTS5

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-005-sqlite-fts`

## Objetivo

Adicionar a projeção FTS5 do índice textual RAG

O handoff exige indexar

- conteúdo
- path
- símbolo
- mensagem Git
- títulos e headings

Busca lexical pública pertence ao RAG-005-C

Ranking lexical pertence ao RAG-005-D

Embeddings continuam proibidos no RAG-005

## Relação com o schema do RAG-005-A

As tabelas relacionais continuam sendo a persistência principal

`rag_documents`

`rag_chunks`

`rag_chunk_symbols`

`rag_index_state`

O FTS5 é uma projeção reconstruível

Ele não substitui essas tabelas

Por isso

`PRAGMA user_version`

permanece em

`1`

O schema relacional v1 não mudou

A projeção possui sua própria constante lógica

`FTS_LAYOUT_VERSION = 1`

## Inicialização explícita

`connect_rag_index`

continua abrindo somente o SQLite relacional

FTS5 não nasce no import e não é criado silenciosamente

A criação ocorre somente quando

`initialize_fts5(connection)`

é chamada

## Tabela virtual

Criada

`rag_chunks_fts`

Campos não indexados usados somente como metadados de retorno

- chunk_id
- document_id
- project_id

Campos FTS

- content
- path
- symbol
- git_message
- title
- heading_path

## Símbolos

O campo FTS `symbol` agrega

- rag_chunks.symbol
- rag_chunk_symbols.name
- rag_chunk_symbols.qualified_name
- rag_chunk_symbols.parent

Isso permite encontrar posteriormente nomes simples e hierarquia qualificada

A busca pública ainda não é implementada neste subpasso

## Sincronização

Foram criados triggers para manter a projeção sincronizada quando

- chunk é inserido
- chunk é atualizado
- chunk é excluído
- símbolo é inserido
- símbolo é atualizado
- símbolo é excluído

Exclusão em cascata de documento remove chunk e consequentemente a entrada FTS

## Rebuild

`rebuild_fts5(connection)`

apaga somente a projeção FTS e a reconstrói a partir das tabelas relacionais

Documentos e chunks originais não são alterados

Isso formaliza que FTS não é fonte da verdade

## Tokenizer

Usado

`unicode61 remove_diacritics 2`

A mesma tokenização será usada na fase de busca lexical

A política de consulta exata de identificadores será congelada no RAG-005-C

## FTS5 indisponível

`fts5_available(connection)`

faz probe usando somente tabela virtual TEMP

Se o runtime SQLite não possuir FTS5

`initialize_fts5`

falha explicitamente com

`RagFts5UnavailableError`

Não existe fallback silencioso para LIKE nesta fase

## Integridade

`verify_fts5_integrity`

exige

- tabela virtual FTS5
- seis triggers de sincronização

Falta de parte da projeção gera

`RagFts5IntegrityError`

## Não antecipado

RAG-005-B não implementa

- API pública de busca
- exemplos GetMoveSpeedProvenance
- codebridge_wait
- EXECUTION_V2_WAIT
- ranking
- BM25
- score público
- embeddings
- vetor
- Jina

Esses itens permanecem nos marcos corretos

## Implementação

Criado

`rag/index/fts5.py`

API pública

- FTS_LAYOUT_VERSION
- FTS_TABLE
- FTS_INDEXED_FIELDS
- FTS_METADATA_FIELDS
- REQUIRED_FTS_TRIGGERS
- RagFts5UnavailableError
- RagFts5IntegrityError
- fts5_available
- fts5_table_exists
- fts5_trigger_names
- verify_fts5_integrity
- rebuild_fts5
- initialize_fts5

Atualizado

`rag/index/__init__.py`

## Testes

Criado

`tests/test_rag_fts5.py`

O corpus cobre

- FTS não criado pelo schema base
- disponibilidade do runtime
- tabela virtual
- triggers
- campos exatos do handoff
- backfill de chunks existentes
- content
- path
- chunk symbol
- symbol table
- qualified name
- git_message
- title
- heading_path
- sincronização de insert
- sincronização de update
- sincronização de delete
- cascade de documento
- rebuild
- idempotência
- user_version preservado
- ausência de embedding
- ausência de API de busca e ranking nesta fase

## Critério de aceitação

RAG-005-B está concluído quando

- os seis campos do handoff entram no FTS
- metadados de identidade não são full text
- chunks existentes são backfilled
- alterações posteriores ficam sincronizadas
- símbolos auxiliares entram no campo symbol
- rebuild recupera a projeção
- user_version relacional permanece 1
- FTS5 indisponível falha explicitamente
- nenhum embedding existe
- nenhuma API pública de busca ou ranking foi antecipada
- suíte RAG passa
- diff check passa
