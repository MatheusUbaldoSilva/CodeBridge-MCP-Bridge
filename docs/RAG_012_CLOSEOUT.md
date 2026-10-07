# RAG-012 — Closeout da indexação incremental

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Estado

`RAG-012 ✅ FECHADO`

O critério do handoff foi cumprido

O CodeBridge agora possui manifest persistente decisão por SHA reindexação seletiva remoção de chunks órfãos invalidação seletiva por versão de modelo e prova direta de idempotência

## Base

RAG-012 parte do fechamento do RAG-011

`d184ca0 docs(rag-011): close Git metadata milestone`

## RAG-012-A — Manifest

Commit

`02d1305 feat(rag-012-a): persist incremental index manifest`

Persistência JSON versionada

`MANIFEST_SCHEMA_VERSION=1`

Campos obrigatórios

```text
path
size
mtime_ns
sha256
chunk_ids
model_version
```

Campos de escopo adicionais

```text
project_id
index_kind
```

Index kinds

```text
TEXT
CODE
```

O manifest possui

- chave determinística
- get
- upsert
- remove
- load
- save atômico por arquivo temporário + replace
- schema_version explícita

## RAG-012-B — Arquivo inalterado

Commit

`279a6bf feat(rag-012-b): skip files with unchanged content SHA`

Criado

`SourceFileSnapshot`

com

```text
path
size
mtime_ns
sha256
```

Critério autoritativo

```text
manifest.sha256 == current.sha256
→ não reprocessar
```

Mudança somente de mtime com conteúdo idêntico continua sendo no-op

## RAG-012-C — Arquivo alterado

Commit

`0fd06a3 feat(rag-012-c): reindex only changed files`

Criado

`reindex_changed_file()`

Fluxo

```text
SHA diferente
↓
rechunk somente path alvo
↓
reembed somente path alvo
↓
atualizar somente ManifestEntry alvo
↓
identificar retired_chunk_ids
```

Entradas de outros arquivos permanecem intactas

Arquivo com SHA igual é rejeitado antes de qualquer callback

## RAG-012-D — Arquivo removido

Commit

`69685f0 feat(rag-012-d): remove orphan chunks for missing files`

Criado

`remove_missing_file()`

Fluxo

```text
arquivo registrado ausente
↓
capturar chunk_ids da entrada
↓
delete_chunks(project index_kind chunk_ids)
↓
remover somente a ManifestEntry alvo
```

Arquivo ainda existente não pode ser removido por essa operação

Cópia stale da entrada do manifest também é rejeitada

## RAG-012-E — Mudança de modelo

Commit

`a25aa90 feat(rag-012-e): invalidate only changed model index`

Criado

`invalidate_model_version()`

Regra

```text
project igual
+
index_kind igual
+
model_version diferente
→ invalidar
```

Provas

- mudança CODE preserva TEXT
- mudança TEXT preserva CODE
- outro projeto permanece intacto
- versão igual não dispara remoção

## Prova de idempotência

Commit

`304e472 test(rag-012): prove idempotent incremental indexing`

Criado

`reconcile_existing_file()`

Estados

```text
UNCHANGED
REINDEXED
```

### Repetição de arquivo inalterado

Duas passagens consecutivas com mesmo SHA

```text
passagem 1 → UNCHANGED
passagem 2 → UNCHANGED
rechunk calls = 0
reembed calls = 0
```

### Arquivo alterado

Primeira passagem com SHA novo

```text
REINDEXED
rechunk = 1
reembed = 1
```

Segunda passagem com o mesmo snapshot

```text
UNCHANGED
rechunk total continua = 1
reembed total continua = 1
```

Isso prova diretamente a indexação idempotente exigida pelo handoff

## Arquitetura consolidada

```text
arquivo atual
↓
SourceFileSnapshot
↓
ManifestEntry existe?
↓
versão do modelo válida?
├── não → invalidar somente TEXT ou CODE correspondente
└── sim
     ↓
SHA igual?
├── sim → UNCHANGED sem trabalho
└── não
     ↓
rechunk somente arquivo
↓
reembed somente arquivo
↓
upsert ManifestEntry
↓
retired_chunk_ids

arquivo não existe?
↓
remover chunks órfãos
↓
remover ManifestEntry
```

## Isolamento

A identidade de manifest inclui

- projeto
- index kind
- path

Assim operações incrementais não misturam

- projetos
- TEXT e CODE
- arquivos diferentes

## Persistência

O manifest é escrito de forma determinística

A mesma estrutura gera o mesmo JSON

Manifest inexistente é tratado como estado vazio

Schema incompatível é rejeitado explicitamente

## Segurança de path

Paths de snapshot e manifest são relativos ao projeto

Escapes com `..` são rejeitados

Nenhuma operação incremental pode apontar silenciosamente para arquivo fora do project root

## Testes

Suíte RAG após a prova de idempotência

```text
Ran 568 tests
OK
```

Incrementos específicos do RAG-012

- RAG-012-A → 11 testes
- RAG-012-B → 7 testes
- RAG-012-C → 5 testes
- RAG-012-D → 4 testes
- RAG-012-E → 5 testes
- idempotência final → 3 testes

Total específico

`35 testes`

Auditorias por fase

```text
git diff --check
OK
```

```text
git diff --cached --check
OK
```

Cada subfase foi commitada e enviada à branch antes de avançar

## Fronteiras preservadas

Não pertencem ao RAG-012

### RAG-013 — Tools MCP

Superfície proposta pelo handoff

```text
codebridge_rag_status
codebridge_rag_index
codebridge_search_context
codebridge_get_context
```

A indexação pesada não deve iniciar silenciosamente

### RAG-014 — Benchmark amplo

Qualidade em perguntas reais corpus real e latência representativa

## Critério de fechamento

RAG-012 pode ser marcado fechado porque

- manifest persiste todos os campos exigidos
- arquivo inalterado por SHA não reprocessa
- arquivo alterado reprocessa somente a própria entrada
- arquivo removido identifica e remove chunks órfãos
- mudança de modelo invalida somente o índice correspondente
- repetição do mesmo estado é no-op
- arquivo alterado reindexa uma vez e depois vira no-op
- suíte RAG passou
- diff checks passaram
- commits A B C D E existem
- prova de idempotência possui commit próprio
- branch está sincronizada com origin antes do closeout

## Próximo marco

`RAG-013 — Tools MCP`

Primeiro passo oficial

`RAG-013-A — rag_status`

Expor inicialmente

- índice
- projetos
- modelos
- loaded/unloaded
- backend
- CPU/GPU
- última indexação
