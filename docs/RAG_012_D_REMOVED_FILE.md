# RAG-012-D — Arquivo removido e chunks órfãos

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Quando um arquivo registrado no manifest deixar de existir remover sua entrada e os chunks órfãos correspondentes

Requisito do handoff

`Arquivo removido → remover chunks órfãos`

## Operação

Criado

`remove_missing_file()`

Entrada

- manifest atual
- ManifestEntry registrada
- project_root
- callback explícito de remoção de chunks

## Pré-condições

A entrada recebida precisa ser exatamente a entrada atualmente registrada no manifest

O arquivo precisa realmente estar ausente no filesystem

Se o arquivo ainda existir a operação falha antes de chamar qualquer remoção

## Fluxo

```text
ManifestEntry
↓
arquivo existe?
├── sim → rejeitar remoção
└── não
     ↓
  delete_chunks(project index_kind chunk_ids)
     ↓
  remover somente a entrada alvo do manifest
```

## Chunks órfãos

Todos os chunk ids associados à entrada removida são enviados ao callback de exclusão

A operação preserva

- project_id
- index_kind
- lista exata dos chunk ids

Isso permite que a camada de storage remova somente os vetores do espaço correto

## Manifest

Depois da remoção

- entrada do arquivo removido desaparece
- outras paths permanecem intactas
- outros projetos permanecem intactos
- outro index_kind permanece intacto

## Entry stale

Se o chamador tentar remover usando uma cópia antiga da ManifestEntry que não corresponde mais ao manifest atual a operação é rejeitada

Isso evita excluir chunks com base em estado ultrapassado

## Entrada sem chunks

Se uma entrada válida não possui chunk ids

- nenhum callback de delete é chamado
- a entrada ainda é removida do manifest

## Provas

Os testes validam

- arquivo realmente ausente
- callback recebe chunks órfãos exatos
- somente a entrada alvo é removida
- arquivo existente não pode ser removido
- entry desatualizada é rejeitada
- entrada sem chunks não dispara delete vazio

## Arquivos

Atualizado

`rag/index/incremental.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_incremental_removed.py`

Criado

`docs/RAG_012_D_REMOVED_FILE.md`

## Fronteiras

RAG-012-D recebe callback de exclusão e não assume backend específico

A integração física com Qdrant ou outro backend continua separada da política incremental

Mudança de modelo pertence ao RAG-012-E

## Critério de aceitação

RAG-012-D está concluído quando

- arquivo ausente é detectado
- chunks da entrada são identificados como órfãos
- callback recebe apenas esses chunks
- entrada do manifest é removida
- entradas não relacionadas permanecem intactas
- arquivo existente não é apagado por engano
- testes específicos passam
- suíte RAG passa
- git diff check passa
