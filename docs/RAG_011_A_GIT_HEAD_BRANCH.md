# RAG-011-A — Estado Git HEAD e branch

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-011-git-metadata`

## Objetivo

Anexar ao chunk o estado Git básico do repositório no momento da indexação

Requisito do handoff

`Anexar estado Git ao chunk`

Nesta fase o estado mínimo é

- repository root
- HEAD commit
- branch atual
- detached HEAD explícito no objeto de captura

## Coleta

Criado

`capture_git_head_state()`

A coleta executa somente comandos Git de leitura

```text
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
```

Nenhum comando de mutação é executado

Nenhum checkout add commit reset ou clean é realizado pelo módulo

## Contrato

`GitHeadState`

contém

```text
repository_root
head_commit
branch
detached
```

HEAD deve ser SHA Git canônico de 40 caracteres hexadecimais lowercase

Quando o repositório está em branch normal

```text
branch=<nome>
detached=False
```

Quando HEAD está detached

```text
branch=None
detached=True
```

## Anexação ao metadata

Criado

`attach_git_head_state_to_metadata()`

O contrato existente `SourceMetadata` já possuía

`git_branch`

`git_commit`

Portanto nenhuma quebra de schema foi necessária

A função cria novo objeto imutável preservando os demais campos

## Anexação ao chunk

Criado

`attach_git_head_state_to_chunk()`

Fluxo

```text
Chunk original
↓
SourceMetadata original
↓
GitHeadState
↓
novo SourceMetadata
  git_branch = branch atual
  git_commit = HEAD
↓
novo Chunk
```

O chunk original não é mutado

## Detached HEAD

Em detached HEAD o chunk recebe

```text
git_branch=None
git_commit=<HEAD>
```

O objeto `GitHeadState` mantém

`detached=True`

Assim o estado de captura continua explícito sem inventar nome de branch

## Subdiretório

A coleta pode começar em subdiretório do projeto

`git rev-parse --show-toplevel`

resolve o root real antes de capturar HEAD e branch

## Erros

Falha de Git é convertida em

`GitStateError`

Exemplos

- diretório fora de repositório
- Git indisponível
- HEAD inválido

Nenhum fallback inventa commit ou branch

## Provas

Os testes usam repositório Git temporário real

São validados

- branch `rag-test`
- HEAD real
- repository root
- captura a partir de subdiretório
- detached HEAD
- erro fora de repositório
- anexação a SourceMetadata
- anexação a Chunk
- imutabilidade do chunk original
- validação de estados impossíveis

## Arquivos

Criado

`rag/sources/git_state.py`

Atualizado

`rag/sources/__init__.py`

Criado

`tests/test_rag_git_head_state.py`

Criado

`docs/RAG_011_A_GIT_HEAD_BRANCH.md`

## Fronteiras

RAG-011-A não tenta descobrir o último commit específico do arquivo

Isso pertence ao RAG-011-B

RAG-011-A não avalia arquivos modificados no working tree

Isso pertence ao RAG-011-C

RAG-011-A não marca resultado stale

Isso pertence ao RAG-011-D

## Critério de aceitação

RAG-011-A está concluído quando

- root Git é resolvido
- HEAD real é capturado
- branch real é capturada
- detached HEAD é representado
- estado é anexado ao metadata
- estado é anexado ao chunk
- original permanece imutável
- falha fora de repo é estruturada
- testes específicos passam
- suíte RAG passa
- git diff check passa
