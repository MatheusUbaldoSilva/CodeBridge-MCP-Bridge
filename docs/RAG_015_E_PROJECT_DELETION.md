# RAG-015-E — Exclusão segura de projeto/index

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Objetivo

Permitir remover os dados derivados de um projeto do RAG sem tocar nos arquivos originais

Requisito do handoff

`Permitir remover projeto/índice sem tocar nos arquivos originais`

## Princípio

O CodeBridge mantém coleções e bancos compartilhados entre projetos

Por isso a exclusão segura não apaga o storage inteiro

Ela remove somente o namespace lógico solicitado

```text
project_id
↓
SQLite rows desse projeto
Qdrant points desse project_namespace
manifest entries desse projeto
↓
fontes originais permanecem intactas
```

## API

Criado

`rag/index/purge.py`

Função pública

`delete_project_index()`

Resultado estruturado

`ProjectIndexDeletionResult`

Campos

```text
project_id
sqlite_documents_deleted
sqlite_chunks_deleted
sqlite_symbols_deleted
sqlite_state_deleted
text_vectors_deleted
code_vectors_deleted
manifest_entries_deleted
total_vectors_deleted
total_sqlite_rows_deleted
```

## SQLite

Antes da remoção são contados

- documents
- chunks
- symbols
- index state

A exclusão principal usa

`DELETE FROM rag_documents WHERE project_id = ?`

O schema existente possui foreign keys

```text
rag_documents
↓ ON DELETE CASCADE
rag_chunks
↓ ON DELETE CASCADE
rag_chunk_symbols
```

Depois é removido

`rag_index_state`

somente para o projeto solicitado

A função confirma no final que não restou linha SQLite daquele namespace

## FTS5

O FTS5 existente acompanha `rag_chunks` por triggers

O teste negativo verifica que depois da exclusão

a busca lexical do projeto removido retorna vazio

enquanto o outro projeto continua pesquisável

## Qdrant

As collections

```text
text
code
```

são compartilhadas

Elas nunca são dropadas para excluir um projeto

A exclusão usa obrigatoriamente

`build_project_namespace_filter(project_id)`

e um

`FilterSelector`

para apagar apenas os points daquele namespace

Antes e depois é executado count exato

Se ainda restar point daquele projeto a operação falha

## Manifest

Adicionado

`IndexManifest.remove_project(project_id)`

Ele remove todas as entries TEXT e CODE do projeto solicitado e preserva os demais namespaces

O manifest só é regravado quando realmente existe entrada a remover

Manifest inexistente continua inexistente

## Fontes originais

A API de exclusão não recebe `project_root` nem path de source files

Ela recebe somente

- conexão SQLite
- Qdrant client
- project_id
- manifest opcional

Portanto o caminho de exclusão não possui motivo nem API para apagar source files

O teste ainda prova isso explicitamente

Arquivos sentinela de projeto A e B têm

- bytes capturados
- mtime capturado

antes da exclusão

Depois da exclusão ambos continuam existentes com bytes e mtime idênticos

## Multi-project

O teste cria simultaneamente

```text
project A = codebridge
project B = drones
```

ambos em

- mesmo SQLite
- mesmo FTS5
- mesmas collections Qdrant
- mesmo manifest

Ao apagar project A

project B permanece em todos os storages

Isso também prova que excluir um projeto não pode ser implementado como drop global das collections

## Idempotência

A exclusão foi executada duas vezes para o mesmo projeto

Primeira chamada remove os dados

Segunda chamada retorna contagens zero

Nenhuma fonte é tocada em nenhuma das duas chamadas

## Namespace inválido

Projeto não canônico como

`CodeBridge`

é rejeitado antes da exclusão

Os dados existentes permanecem intactos

## Testes negativos

Criado

`tests/test_rag_015_project_deletion.py`

Casos

1. remove somente derived data do project A
2. project B permanece no SQLite
3. project B permanece no FTS5
4. project B permanece na collection text
5. project B permanece na collection code
6. collections compartilhadas não são dropadas
7. manifest remove somente entries de A
8. source A permanece byte a byte
9. source B permanece byte a byte
10. mtime dos sources permanece igual
11. segunda exclusão é idempotente
12. namespace inválido é rejeitado antes de apagar

Execução observada

```text
Ran 5 tests in 1.291s
OK
```

## Arquivos

Criado

`rag/index/purge.py`

Atualizado

`rag/index/manifest.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_015_project_deletion.py`

Criado

`docs/RAG_015_E_PROJECT_DELETION.md`

## Critério de aceitação

RAG-015-E está concluído quando

- projeto pode ser removido do SQLite
- FTS acompanha a remoção
- text vectors do projeto são removidos
- code vectors do projeto são removidos
- collections compartilhadas permanecem
- outro projeto permanece intacto
- manifest é limpo por namespace
- operação é idempotente
- arquivos fonte não são alterados
- namespace inválido não apaga nada
- testes negativos passam
- suíte RAG passa
- git diff check passa

## Próximo passo

Com RAG-015-A até E concluídos resta a auditoria integral dos testes negativos e o closeout formal do marco RAG-015
