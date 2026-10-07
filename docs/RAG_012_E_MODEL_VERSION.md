# RAG-012-E — Invalidação seletiva por versão do modelo

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Quando a versão de um modelo de embedding mudar invalidar somente o índice correspondente

Requisito do handoff

`Nova versão de embedding deve invalidar somente o índice correspondente`

## Base arquitetural

RAG-012-A adicionou ao manifest

`index_kind`

com espaços

```text
TEXT
CODE
```

e também

`model_version`

Isso permite comparar versão por espaço sem apagar o outro índice

## Operação

Criado

`invalidate_model_version()`

Entrada

- manifest atual
- project_id
- index_kind alvo
- current_model_version
- callback explícito de remoção de chunks

## Seleção

Uma entrada é invalidada somente quando todas as condições são verdadeiras

```text
entry.project_id == project_id
entry.index_kind == index_kind
entry.model_version != current_model_version
```

Entradas de outro projeto não são tocadas

Entradas do outro espaço de embedding não são tocadas

## Exemplo CODE

Manifest

```text
TEXT text-v1
CODE code-v1
```

modelo CODE atual

`code-v2`

Resultado

```text
TEXT text-v1 → preservado
CODE code-v1 → invalidado
```

## Exemplo TEXT

Se somente o modelo TEXT mudar

```text
TEXT → invalidado
CODE → preservado
```

## Versão igual

Se a versão registrada já for a versão atual

- nenhuma entrada é removida
- nenhum chunk é removido
- nenhum callback é chamado

## Chunks

Para cada entrada invalidada os chunk ids são enviados ao callback com

- project_id
- index_kind
- chunk_ids

Depois a entrada é removida do manifest

Isso deixa o espaço pronto para nova indexação usando a nova versão

## Resultado

`ModelInvalidationOutcome`

contém

```text
manifest
invalidated_entries
removed_chunk_ids
```

Assim a invalidação permanece auditável

## Provas

Os testes validam

- mudança CODE invalida apenas CODE
- mudança TEXT preserva CODE
- versão igual não invalida nada
- outro projeto permanece intacto
- versão vazia é rejeitada

## Arquivos

Atualizado

`rag/index/incremental.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_incremental_model_version.py`

Criado

`docs/RAG_012_E_MODEL_VERSION.md`

## Critério de aceitação

RAG-012-E está concluído quando

- versão de modelo é comparada por index_kind
- mudança TEXT não remove CODE
- mudança CODE não remove TEXT
- outro projeto não é afetado
- versão igual não dispara trabalho
- chunks do espaço invalidado são identificados
- testes específicos passam
- suíte RAG passa
- git diff check passa

Com isso RAG-012-A B C D E fica pronto para a prova final de indexação idempotente e closeout
