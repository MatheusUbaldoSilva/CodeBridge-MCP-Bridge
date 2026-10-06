# RAG-002-C — Inventário de fontes Git

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Objetivo

Mapear as informações Git que poderão ser usadas como contexto pelo RAG sem transformar o índice em fonte oficial e sem ampliar a superfície de execução mutável

O handoff exige

```text
branch
HEAD
commit
mensagem
arquivo
diff
histórico relevante
```

Todos os sete itens estão congelados neste subpasso

## Fonte da verdade

O Git real continua sendo a prova de versão

O RAG poderá manter referências e conteúdo recuperável mas qualquer decisão de alteração deve verificar o estado Git atual novamente

Fluxo obrigatório

```text
RAG encontra referência Git
        ↓
Git real é consultado novamente
        ↓
branch HEAD arquivo e working tree são confirmados
        ↓
IA decide
```

## Facetas permitidas

### BRANCH

Campos mínimos

```text
repository
branch
detached
```

Representa a branch observada no momento da coleta

### HEAD

Campos mínimos

```text
repository
head_commit
```

HEAD deve apontar para um commit verificável

### COMMIT

Campos mínimos

```text
repository
commit
parent_commits
authored_at
committed_at
```

O commit é uma referência imutável de proveniência

### MESSAGE

Campos mínimos

```text
repository
commit
message
```

A mensagem sempre deve permanecer ancorada ao SHA do commit correspondente

### FILE

Campos mínimos

```text
repository
commit
path
change_type
blob_sha
```

Arquivo Git não deve ser representado apenas pelo path porque o conteúdo depende do commit

### DIFF

Campos mínimos

```text
repository
base_commit
head_commit
path
patch
```

Diff sempre deve registrar os commits ou refs usados na comparação

Conteúdo de diff futuro deverá respeitar as mesmas regras de exclusão e secrets das fontes normais

### HISTORY

Campos mínimos

```text
repository
scope
commit_refs
```

Histórico relevante significa histórico filtrado por contexto como

- projeto
- path
- arquivo
- símbolo quando disponível
- marco
- consulta

Não significa copiar todo o histórico Git para cada resultado RAG

## Operações Git somente leitura aprovadas conceitualmente

```text
status
branch --show-current
rev-parse
log
show
diff
```

O módulo usa nomes normalizados

```text
status
branch-show-current
rev-parse
log
show
diff
```

Não foi adicionada nova execução Git neste marco

O CodeBridge já possui leitura segura de

```text
GIT_STATUS
GIT_HEAD
GIT_BRANCH
```

em `app_rewrite/read_only_batch.py`

## Operações mutáveis explicitamente fora do RAG-002-C

Exemplos

```text
git add
git commit
git checkout
git switch
git reset
git restore
git merge
git rebase
git cherry-pick
git push
git pull
git clean
```

O RAG não ganha autorização para executar essas operações

## Snapshot Git real usado na validação

Branch auditada

```text
rag-002-source-inventory
```

HEAD antes do commit deste subpasso

```text
037ea25b9aeea76a67be2c6b210ac60bf7831d6a
```

Mensagem

```text
feat(rag-002-b): map code and config source allowlist
```

Sequência recente da frente RAG

```text
037ea25  feat(rag-002-b): map code and config source allowlist
881c734  feat(rag-002-a): map documentary source inventory
2ecaca2  docs(rag-001): close isolated RAG foundation milestone
906001a  test(rag-001-d): prove executor isolation from RAG
4fe08f8  feat(rag-001-c): add testable RAG data contracts
2166b25  docs(rag-001-b): freeze RAG module layout
feb17de  docs(rag-001-a): freeze RAG responsibility contract
8730998  docs: add CodeBridge 2.0 RAG handoff
```

Esse snapshot demonstra branch HEAD commit mensagem e histórico

A inspeção de commits do GitHub também permite recuperar arquivos alterados e diff quando solicitado sem modificar o repositório

## Implementação de inventário

Criado

`rag/sources/git_inventory.py`

Ele contém

- enum `GitFacet`
- mapa `GIT_FACET_FIELDS`
- allowlist `READ_ONLY_GIT_OPERATIONS`
- helpers de consulta do contrato

O módulo não executa Git

## Invariantes

- Git real continua sendo fonte da verdade
- todo resultado Git mantém referência de repositório
- mensagens permanecem ligadas ao commit
- arquivos permanecem ligados a commit e path
- diff mantém base e head
- histórico usa referências e escopo
- nenhuma operação mutável foi aprovada
- nenhuma indexação foi iniciada
- nenhum modelo foi carregado
- executor não foi alterado

## Fora do escopo deste subpasso

Ainda não foram implementados

- coleta Git completa
- armazenamento Git no índice
- chunking de diff
- embedding de mensagens
- busca por histórico
- staleness de working tree
- associação de último commit por linha
- tools MCP RAG

Esses pontos pertencem aos marcos posteriores

## Critério de aceitação do RAG-002-C

RAG-002-C está concluído quando

- as sete facetas do handoff estão mapeadas
- cada faceta possui proveniência mínima
- histórico relevante é diferenciado de cópia integral
- operações Git mutáveis permanecem fora
- estado real da branch foi auditado
- testes determinísticos cobrem o contrato
