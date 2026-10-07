# RAG-012-C — Reindexação somente do arquivo alterado

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Quando o SHA mudar executar rechunk e reembedding somente para o arquivo alterado

Requisito do handoff

`Rechunk + reembedding somente daquele arquivo`

## Orquestração

Criado

`reindex_changed_file()`

A função recebe

- manifest atual
- entrada anterior do arquivo
- snapshot atual
- versão do modelo
- callback de rechunk
- callback de reembedding

## Pré-condições

A operação exige

```text
previous_entry.path == snapshot.path
previous_entry.sha256 != snapshot.sha256
```

Arquivo com SHA igual é rejeitado antes de chamar qualquer callback

Isso preserva o contrato fechado no RAG-012-B

## Fluxo

```text
arquivo alterado
↓
rechunk(snapshot)
↓
novos chunk ids
↓
reembed(snapshot chunks index_kind model_version)
↓
nova ManifestEntry
↓
upsert somente da mesma path
```

Nenhuma outra entrada do manifest é modificada

## Chunks antigos

A saída

`ChangedFileReindexOutcome`

também informa

`retired_chunk_ids`

São os chunk ids existentes antes que deixaram de existir após o novo rechunk

Isso prepara remoção seletiva dos vetores antigos sem apagar chunks ainda reutilizados

## Prova de isolamento

O teste usa manifest com

```text
src/a.py
src/b.py
```

somente `src/a.py` tem SHA alterado

Callbacks observados

```text
rechunk src/a.py
reembed src/a.py
```

A entrada de `src/b.py` permanece byte a byte igual no objeto de manifest

## Validações

- path divergente é rejeitado
- SHA igual é rejeitado
- chunk ids vazios são rejeitados
- chunk ids duplicados são rejeitados
- reembedding só ocorre depois do rechunk válido

## Arquivos

Atualizado

`rag/index/incremental.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_incremental_changed.py`

Criado

`docs/RAG_012_C_CHANGED_FILE.md`

## Fronteiras

RAG-012-C identifica chunks aposentados mas não executa remoção de arquivo inteiro

Arquivo removido pertence ao RAG-012-D

Mudança de modelo pertence ao RAG-012-E

## Critério de aceitação

RAG-012-C está concluído quando

- SHA alterado dispara rechunk
- o mesmo arquivo dispara reembedding
- outro arquivo não é tocado
- manifest atualiza somente a entrada alvo
- chunks aposentados são identificados
- testes específicos passam
- suíte RAG passa
- git diff check passa
