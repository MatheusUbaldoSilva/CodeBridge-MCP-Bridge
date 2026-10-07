# RAG-012 — Prova de indexação idempotente

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Cumprir o critério final do handoff

`RAG-012 ✅ com indexação idempotente`

## Reconcile de arquivo existente

Criado

`reconcile_existing_file()`

A operação exige que a versão do modelo já esteja compatível

Se a versão divergir o chamador precisa executar a invalidação seletiva do RAG-012-E primeiro

## Arquivo inalterado

Quando

```text
manifest.sha256 == snapshot.sha256
```

resultado

`UNCHANGED`

Nenhum callback de rechunk é chamado

Nenhum callback de reembedding é chamado

O manifest permanece exatamente igual

Repetir a mesma reconciliação continua sendo no-op

## Arquivo alterado

Primeira passagem com SHA novo

```text
REINDEXED
↓
rechunk uma vez
↓
reembed uma vez
↓
manifest recebe novo SHA e novos chunk ids
```

Segunda passagem com o mesmo snapshot

```text
UNCHANGED
```

Sem novo rechunk

Sem novo reembedding

Isso prova idempotência operacional do estado incremental

## Prova automatizada

O teste

`test_changed_pass_runs_once_then_next_identical_pass_is_noop`

valida exatamente

```text
primeira passagem alterada
calls = [rechunk reembed]

segunda passagem idêntica
calls continuam [rechunk reembed]
```

Também é validado

- duas passagens inalteradas não fazem trabalho
- mudança de versão de modelo é rejeitada até a invalidação seletiva apropriada

## Arquivos

Atualizado

`rag/index/incremental.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_012_idempotent_indexing.py`

Criado

`docs/RAG_012_IDEMPOTENCE.md`

## Resultado

O pipeline incremental agora possui prova direta de que executar novamente o mesmo estado não repete rechunk nem reembedding
