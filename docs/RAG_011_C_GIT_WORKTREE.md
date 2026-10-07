# RAG-011-C — Estado do working tree por arquivo

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-011-git-metadata`

## Objetivo

Não confundir um chunk indexado anteriormente com o estado atual do arquivo no working tree

Requisito do handoff

`Não confundir índice antigo com working tree atual`

## Decisão

O estado atual do arquivo passa a ser capturado separadamente do histórico Git

Novo campo opcional em `SourceMetadata`

`git_worktree_status`

Ele não substitui

- git_branch
- git_commit HEAD
- git_provenance_commit

Cada campo responde uma pergunta diferente

```text
git_branch
→ em qual branch o repositório estava

git_commit
→ qual era o HEAD capturado

git_provenance_commit
→ qual commit histórico é relevante ao arquivo ou trecho

git_worktree_status
→ qual é o estado atual do arquivo fora do commit
```

## Captura

Criado

`capture_git_path_state()`

A operação é somente leitura e usa

```text
git status --porcelain=v1 --untracked-files=all -- <path>
```

A consulta é limitada ao path solicitado

## Estados canônicos

`GitPathStatus`

pode assumir

```text
CLEAN
MODIFIED
STAGED
STAGED_AND_MODIFIED
UNTRACKED
DELETED
RENAMED
TYPE_CHANGED
CONFLICTED
```

## Semântica

### CLEAN

Nenhuma alteração de index ou working tree para o path

### MODIFIED

Arquivo rastreado alterado somente no working tree

### STAGED

Alteração presente no index Git

### STAGED_AND_MODIFIED

Existe uma versão staged e outra modificação posterior no working tree

### UNTRACKED

Arquivo ainda não pertence a nenhum commit

### DELETED

Path rastreado removido

### RENAMED

Git reporta rename ou copy no status do path

### TYPE_CHANGED

Mudança de tipo de objeto

### CONFLICTED

Estado de merge não resolvido

## XY preservado

Além do estado canônico o objeto

`GitPathState`

preserva

- index_code
- worktree_code
- raw_status

Isso mantém informação suficiente para auditoria futura sem obrigar o restante do RAG a interpretar diretamente porcelain Git

## Dirty

`GitPathState.dirty`

é falso somente para

`CLEAN`

Todos os demais estados são tratados como working tree diferente do commit

## Anexação ao metadata

`attach_git_path_state_to_metadata()`

preenche

`git_worktree_status`

preservando os campos históricos

Exemplo

```text
git_branch=rag-test
git_commit=<HEAD>
git_provenance_commit=<commit do arquivo>
git_worktree_status=MODIFIED
```

Assim o sistema não precisa escolher entre histórico e estado atual

## Anexação ao chunk

`attach_git_path_state_to_chunk()`

cria novo Chunk imutável com o metadata atualizado

O chunk original permanece intacto

## Path seguro

Path absoluto é aceito somente quando fica dentro do repository root

Path externo é rejeitado

O path armazenado é relativo e normalizado

## Provas reais

Os testes criam repositórios Git temporários reais e validam

- arquivo clean
- modificação unstaged
- modificação staged
- staged mais nova modificação unstaged
- arquivo untracked
- arquivo deletado
- path absoluto dentro do repositório
- path externo rejeitado
- erro fora de repositório
- anexação preservando HEAD e provenance
- imutabilidade do chunk
- conflito de path rejeitado

## Contrato atualizado

`SourceMetadata`

agora possui

```text
git_branch
git_commit
git_provenance_commit
git_worktree_status
```

## Helper de chunking

`attach_source_provenance()`

passou a aceitar opcionalmente

`git_worktree_status`

Isso permite que um pipeline já auditado construa o chunk com o estado Git atual preservado

## Arquivos

Criado

`rag/sources/git_worktree.py`

Atualizado

`rag/sources/__init__.py`

Atualizado

`rag/contracts.py`

Atualizado

`rag/chunking/provenance.py`

Criado

`tests/test_rag_git_worktree.py`

Criado

`docs/RAG_011_C_GIT_WORKTREE.md`

## Fronteiras

RAG-011-C não decide se o conteúdo indexado está stale

Um arquivo MODIFIED pode ter alteração fora do intervalo do chunk

A decisão de staleness por SHA pertence ao RAG-011-D

RAG-011-C não reindexa arquivo modificado

Isso pertence ao RAG-012

## Critério de aceitação

RAG-011-C está concluído quando

- working tree é consultado por path
- clean é distinguido de modificado
- staged e unstaged são separados
- untracked e deleted são reconhecidos
- estado atual não sobrescreve HEAD
- estado atual não sobrescreve commit de proveniência
- metadata e chunk podem receber o estado
- testes específicos passam
- suíte RAG passa
- git diff check passa
