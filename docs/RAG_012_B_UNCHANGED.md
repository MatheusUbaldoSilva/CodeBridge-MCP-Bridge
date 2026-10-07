# RAG-012-B — Arquivo inalterado não reprocessa

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-012-incremental-index`

## Objetivo

Pular rechunk e reembedding quando o conteúdo do arquivo continua igual ao registrado no manifest

Requisito do handoff

`SHA igual → não reprocessar`

## Snapshot atual

Criado

`SourceFileSnapshot`

contendo

```text
path
size
mtime_ns
sha256
```

Criado

`capture_source_file_snapshot()`

A função captura os metadados atuais do arquivo e calcula SHA-256 dos bytes reais do arquivo

## SHA como autoridade

A decisão de pular reprocessamento usa

`sha256`

e não somente size ou mtime

Função

`should_skip_file_reprocessing()`

retorna verdadeiro somente quando

```text
manifest.sha256 == current.sha256
```

## mtime não força reprocessamento

O handoff define SHA igual como critério de arquivo inalterado

Por isso alterar somente mtime mantendo os mesmos bytes continua retornando

`skip=True`

size e mtime permanecem no manifest para auditoria e otimizações futuras mas não substituem a prova de conteúdo

## Conteúdo alterado

Quando o SHA diverge

`skip=False`

RAG-012-B não executa o reprocessamento

RAG-012-C será responsável por limitar rechunk e reembedding ao arquivo alterado

## Segurança de path

Snapshot aceita somente path relativo dentro de project_root

Escape com `..` é rejeitado

Arquivo ausente gera `FileNotFoundError`

RAG-012-D tratará arquivo removido na reconciliação do manifest

## Provas

Os testes validam

- captura de path size mtime e SHA
- mesmo SHA pula reprocessamento
- mtime diferente com mesmo SHA ainda pula
- conteúdo alterado não pula
- path incompatível entre manifest e snapshot é rejeitado
- arquivo ausente falha explicitamente
- path externo é rejeitado

## Arquivos

Criado

`rag/index/incremental.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_incremental_unchanged.py`

Criado

`docs/RAG_012_B_UNCHANGED.md`

## Fronteiras

RAG-012-B não reindexa arquivo alterado

RAG-012-B não remove chunks de arquivo removido

RAG-012-B não invalida por mudança de modelo

Esses comportamentos ficam em RAG-012-C D E

## Critério de aceitação

RAG-012-B está concluído quando

- snapshot atual pode ser capturado
- SHA atual é calculado
- SHA igual retorna skip
- mudança somente de mtime continua skip
- SHA diferente retorna não skip
- testes específicos passam
- suíte RAG passa
- git diff check passa
