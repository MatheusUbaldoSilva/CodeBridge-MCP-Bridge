# RAG-015-D — Conteúdo indexado e origem de chunks

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-015-security`

## Objetivo

Garantir que todo chunk indexável tenha origem verificável

Requisito do handoff

`Registrar origem de todo chunk`

## Base já existente

RAG-003-D já congelou a proveniência obrigatória dos chunks textuais

Campos mínimos

- project_id
- source_type
- path
- line_start
- line_end
- SHA-256 da fonte
- indexed_at com timezone

Git e source_id continuam opcionais quando não existem

## Reforço de segurança

Foi criado

`ChunkOriginRecord`

e a API

`require_chunk_origin(chunk)`

Essa API valida explicitamente se um Chunk possui a proveniência mínima antes de ser considerado originado

## Contrato de origem

`ChunkOriginRecord`

registra

```text
chunk_id
document_id
project_id
source_type
path
line_start
line_end
sha256
indexed_at
source_id
```

O conteúdo do chunk não é duplicado no registro de origem

O objetivo é rastreabilidade e não uma segunda cópia do conteúdo

## Validações obrigatórias

`require_chunk_origin()`

rejeita chunk sem

- path
- line_start
- line_end
- SHA-256
- indexed_at

Também rejeita path traversal

Separadores Windows são normalizados para POSIX

```text
docs\security.md
↓
docs/security.md
```

## Integração com criação oficial de chunks

`attach_source_provenance()`

agora chama

`require_chunk_origin()`

antes de devolver cada Chunk

Fluxo

```text
draft
↓
verificação contra fonte real
↓
SourceMetadata
↓
Chunk
↓
require_chunk_origin
↓
Chunk liberado
```

Assim o caminho oficial de criação não consegue emitir silenciosamente um chunk sem origem mínima

## Auditoria de construção

Auditoria do pacote `rag/` mostrou que a construção de `Chunk` de produção ocorre em

`rag/chunking/provenance.py`

Os outros usos encontrados estão em testes

Isso mantém um único ponto de criação de chunks originados

## Persistência

Foi provado round-trip real

```text
attach_source_provenance
↓
ChunkOriginRecord
↓
SQLite rag_documents/rag_chunks
↓
FTS5
↓
SearchResult
```

Depois do round-trip foram preservados

- path
- line_start
- line_end
- sha256
- indexed_at
- source_id

## Testes negativos

Criado

`tests/test_rag_015_chunk_origin.py`

Casos de rejeição

- sem path
- sem line range
- sem SHA-256
- sem indexed_at
- path traversal

Casos positivos

- proveniência oficial completa
- Windows path normalizado
- source_id preservado
- origem sobrevive ao SQLite + FTS5
- registro de origem não replica conteúdo

Execução observada

```text
Ran 9 tests in 0.100s
OK
```

## Alterações

Atualizado

`rag/chunking/provenance.py`

Atualizado

`rag/chunking/__init__.py`

Criado

`tests/test_rag_015_chunk_origin.py`

Criado

`docs/RAG_015_D_CHUNK_ORIGIN.md`

## Critério de aceitação

RAG-015-D está concluído quando

- todo chunk emitido pelo caminho oficial possui origem
- origem contém projeto e source_type
- origem contém path
- origem contém faixa de linhas
- origem contém SHA-256
- origem contém indexed_at
- traversal é rejeitado
- origem permanece após persistência e retrieval
- testes negativos passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-015-E — Exclusão`

Permitir remover projeto ou índice sem tocar nos arquivos originais e provar isso com teste negativo
