# RAG-011 — Closeout de metadados Git e staleness

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-011-git-metadata`

## Estado

`RAG-011 ✅ FECHADO`

O critério do handoff foi cumprido

O CodeBridge agora consegue capturar HEAD e branch associar commit histórico relevante ao arquivo ou trecho distinguir working tree atual do histórico e marcar resultado stale quando o SHA do conteúdo indexado diverge do arquivo atual

## Base

RAG-011 parte do fechamento do RAG-010

`f0dd57c docs(rag-010): close hybrid search milestone`

## RAG-011-A — HEAD e branch

Commit

`9673588 feat(rag-011-a): attach Git HEAD and branch metadata`

Captura read-only

```text
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
```

Contrato

`GitHeadState`

preserva

- repository_root
- head_commit
- branch
- detached

Anexação ao chunk usa os campos já existentes

```text
git_branch
git_commit
```

Nesta arquitetura `git_commit` representa o HEAD capturado no momento da indexação

Detached HEAD é representado sem inventar nome de branch

## RAG-011-B — Commit de proveniência

Commit

`5fc54e4 feat(rag-011-b): attach Git file and range provenance`

Novo campo de contrato

`git_provenance_commit`

Semântica

```text
git_commit
→ HEAD global capturado

git_provenance_commit
→ último commit relevante ao arquivo ou trecho
```

Captura por arquivo

```text
git log -1 --format=%H -- <path>
```

Captura preferencial por trecho

```text
git log -1 --format=%H -L <start>,<end>:<path>
```

Se a resolução por linhas não for possível existe fallback para proveniência do arquivo inteiro

Arquivo untracked retorna `None`

Nenhum commit é inventado

### Prova real de trecho

Repositório temporário com dois commits

Primeiro commit contém quatro linhas

Segundo commit altera somente a linha 2

Resultado

- linha 2 → segundo commit
- linha 4 → primeiro commit
- arquivo inteiro → segundo commit

Isso prova diferença entre HEAD global e commit historicamente relevante ao trecho

## RAG-011-C — Working tree

Commit

`427dca0 feat(rag-011-c): track Git working tree path state`

Novo campo de contrato

`git_worktree_status`

Estados canônicos

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

Consulta read-only

```text
git status --porcelain=v1 --untracked-files=all -- <path>
```

O estado atual não sobrescreve

- branch
- HEAD
- commit de proveniência

Assim o índice histórico e o working tree atual permanecem conceitos separados

Testes reais cobrem

- clean
- modificado unstaged
- staged
- staged + modificado novamente
- untracked
- deleted

## RAG-011-D — Staleness

Commit

`a7607e6 feat(rag-011-d): mark stale results from source SHA`

Contrato usado

`SourceMetadata.sha256`

Fluxo

```text
SHA indexado
+
arquivo atual
↓
SHA atual
↓
comparação
```

Estados

```text
FRESH
STALE
UNKNOWN
```

FRESH

`SHA_MATCH`

STALE

```text
SHA_MISMATCH
FILE_MISSING
NOT_A_FILE
```

UNKNOWN

```text
PATH_UNAVAILABLE
INDEXED_SHA_UNAVAILABLE
READ_FAILED
```

O resultado estruturado

`StalenessEvaluation`

pode ser aplicado ao contrato existente

`SearchResult.stale`

através de

`mark_search_result_staleness()`

## Teste obrigatório do handoff

O handoff exige

`RAG-011 ✅ com teste de arquivo alterado após indexação`

O teste

`test_file_changed_after_indexing_is_stale`

executa

```text
criar arquivo
↓
capturar SHA indexado
↓
alterar arquivo
↓
calcular SHA atual
↓
SHA diverge
↓
STALE
```

Resultado

`PASS`

## Contrato consolidado de metadata Git

`SourceMetadata`

possui agora

```text
git_branch
git_commit
git_provenance_commit
git_worktree_status
sha256
```

Semântica

```text
git_branch
→ branch de captura

git_commit
→ HEAD de captura

git_provenance_commit
→ commit histórico relevante ao arquivo/trecho

git_worktree_status
→ estado atual do path no working tree

sha256
→ fingerprint do conteúdo indexado
```

Esses campos não são tratados como sinônimos

## Imutabilidade

Helpers de anexação usam novos objetos imutáveis

Chunks e metadados originais não são modificados silenciosamente

## Segurança de paths

As operações de Git e staleness normalizam paths relativos ao repository root

Paths absolutos são aceitos somente quando continuam dentro do repositório

Tentativas de escape com path externo ou `..` são rejeitadas

## Persistência

Os campos históricos já existentes `git_branch` e `git_commit` continuam compatíveis com o schema atual

Os novos campos `git_provenance_commit` e `git_worktree_status` estão congelados no contrato de `SourceMetadata` e no pipeline de construção de chunks

RAG-011 não introduz migração destrutiva do banco SQLite existente

A persistência incremental e o manifest pertencem ao RAG-012

## Testes

Suíte RAG após RAG-011-D

```text
Ran 533 tests
OK
```

Incrementos específicos

- RAG-011-A → 8 testes
- RAG-011-B → 11 testes
- RAG-011-C → 12 testes
- RAG-011-D → 7 testes

Total específico do marco

`38 testes`

Auditorias executadas por fase

```text
git diff --check
OK
```

```text
git diff --cached --check
OK
```

Cada subfase possui commit próprio e push para a branch do marco

## Arquitetura consolidada

```text
arquivo / chunk
↓
HEAD + branch
↓
commit de proveniência arquivo/trecho
↓
working tree status
↓
SHA indexado
↓
comparar com arquivo atual
↓
FRESH / STALE / UNKNOWN
↓
SearchResult.stale
```

## Fronteiras preservadas

Não pertencem ao RAG-011

### RAG-012 — Indexação incremental

- manifest
- path
- size
- mtime
- SHA-256
- chunk ids
- versão do modelo
- pular arquivo inalterado
- reindexar somente arquivo alterado
- remover chunks de arquivo removido
- invalidar somente índice correspondente ao modelo alterado

RAG-011 detecta e descreve o estado

RAG-012 decidirá e executará a atualização do índice

## Critério de fechamento

RAG-011 pode ser marcado fechado porque

- HEAD e branch são capturados
- detached HEAD é representado
- commit de proveniência de arquivo existe
- commit de proveniência de trecho existe quando Git permite
- fallback por arquivo existe
- working tree é classificado separadamente
- SHA atual é comparado ao SHA indexado
- SearchResult pode ser marcado stale
- teste de arquivo alterado após indexação passou
- suíte RAG passou
- diff checks passaram
- commits A B C D existem
- branch foi sincronizada após cada subfase

## Próximo marco

`RAG-012 — Indexação incremental`

Primeiro passo oficial

`RAG-012-A — Manifest`

Persistir

```text
path
size
mtime
SHA-256
chunk ids
versão do modelo
```
