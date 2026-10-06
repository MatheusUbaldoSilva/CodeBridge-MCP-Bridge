# Fechamento — RAG-002 — Inventário de fontes

Data: 2026-10-06  
Projeto: CodeBridge 2.0 — MCP Bridge  
Branch: `rag-002-source-inventory`

## Status

RAG-002-A ✅  
RAG-002-B ✅  
RAG-002-C ✅  
RAG-002-D ✅  
RAG-002-E ✅  

Resultado: **RAG-002 FECHADO**

## Objetivo do marco

Congelar quais fontes poderão alimentar o RAG antes de qualquer chunking indexação lexical embedding ou carregamento de modelos

O marco cobre

- documentação
- código e configuração
- Git
- execuções e auditorias
- exclusões e secrets

## RAG-002-A — Fontes documentais

Implementado em

`rag/sources/document_inventory.py`

Categorias congeladas

```text
README
DOCUMENTATION
HANDOFF
ROADMAP
PATCH_NOTE
AUDIT
```

Snapshot auditado

```text
README        = 2
DOCUMENTATION = 6
HANDOFF       = 1
ROADMAP       = 1
PATCH_NOTE    = 0
AUDIT         = 0
```

Total documental elegível no snapshot inicial

```text
10
```

Manifestos `requirements.txt` não foram confundidos com documentação

## RAG-002-B — Código e configuração

Implementado em

`rag/sources/code_inventory.py`

Allowlist congelada

```text
.c
.cc
.cpp
.h
.hpp
.py
.ps1
.bat
.cmd
.sh
.js
.ts
.json
.yaml
.yml
.toml
.html
.css
.nsi
.nsh
```

Manifesto especial

```text
requirements.txt
```

A permissão de `requirements.txt` é pelo nome exato

TXT genérico não virou código

Snapshot inicial

```text
115 fontes técnicas elegíveis
```

## RAG-002-C — Git

Implementado em

`rag/sources/git_inventory.py`

Facetas congeladas

```text
BRANCH
HEAD
COMMIT
MESSAGE
FILE
DIFF
HISTORY
```

Operações conceitualmente somente leitura

```text
status
branch-show-current
rev-parse
log
show
diff
```

Nenhuma operação Git mutável foi aprovada

Git real continua sendo a fonte da verdade

## RAG-002-D — Execuções e auditorias

Implementado em

`rag/sources/execution_inventory.py`

Campos permitidos

```text
execution_id
target
command_hash
status
structured_error
summary
raw_reference
```

O RAW continua no ledger

A referência é feita por

```text
execution_id
raw_available
```

Conteúdo não copiado automaticamente

```text
output
stdout
stderr
text
stdout_delta
stderr_delta
failed_command
important_sections
execution_output_chunks
raw
raw_output
```

O ledger continua sendo fonte oficial das execuções

## RAG-002-E — Exclusões

Implementado em

`rag/sources/exclusion_policy.py`

Denylist cobre

```text
.git/objects
.venv
venv
node_modules
build
dist
caches
binários
backups
temporários
credenciais
.env
chaves privadas
tokens
path traversal
```

Regra congelada

```text
denylist vence allowlist
```

Portanto um arquivo `.py` `.json` `.js` ou `.md` continua bloqueado se estiver em uma origem negada

## Testes adicionados no RAG-002

```text
tests/test_rag_document_inventory.py
tests/test_rag_code_inventory.py
tests/test_rag_git_inventory.py
tests/test_rag_execution_inventory.py
tests/test_rag_exclusion_policy.py
```

Também permanecem preservados os testes do RAG-001

```text
tests/test_rag_contracts.py
tests/test_rag_isolation.py
```

## Validação do RAG-002-E

A lógica exata da denylist foi executada isoladamente com 37 casos de exclusão

Resultado

```text
casos testados = 37
falhas = 0
fontes legítimas bloqueadas = 0
```

Foram confirmados entre outros

- `.git/objects`
- ambientes virtuais
- node_modules
- build e dist
- caches
- binários
- backups
- temporários
- env files
- credenciais
- chaves privadas
- tokens
- path traversal
- paths Windows

Também foram validados os artefatos reais

```text
installer/dist/CodeBridge-Setup.exe
installer/dist/CodeBridge-Setup.sha256
```

Ambos foram negados por `dist/`

## Observação sobre execução da suíte no PC

Durante a validação deste marco o catálogo do conector CodeBridge exibiu tools de terminal que o runtime respondeu como desconhecidas

Exemplo observado

```text
Unknown tool: codebridge_terminal
```

Por isso não foi usado um caminho legado nem foi afirmada uma execução completa no PC que não ocorreu

O ambiente isolado desta sessão também não conseguiu resolver `github.com` por DNS para fazer clone direto

As validações foram realizadas com

- conteúdo exato auditado via conector GitHub
- revisão pós commit
- testes isolados determinísticos das políticas
- testes previamente executados nos subpassos

A suíte versionada permanece pronta para execução em um checkout normal assim que a superfície MCP ativa estiver consistente

## Commits preservados do RAG-002

```text
881c734  feat(rag-002-a): map documentary source inventory
037ea25  feat(rag-002-b): map code and config source allowlist
2e4d787  feat(rag-002-c): map Git source inventory
8867118  feat(rag-002-d): map execution ledger source contract
335431a  feat(rag-002-e): enforce source denylist
```

## Invariantes confirmados

1. nenhuma fonte entra apenas por extensão sem passar pela política
2. denylist sempre vence allowlist
3. Git continua sendo fonte de verdade para versão
4. ledger continua sendo fonte de verdade para execução
5. RAW não é duplicado automaticamente
6. failed_command não é indexado automaticamente
7. secrets explícitos por path são negados
8. path traversal é negado
9. nenhuma indexação foi iniciada
10. nenhum chunk foi criado
11. nenhum embedding foi gerado
12. nenhum modelo Jina foi carregado
13. executor MCP não foi alterado

## Próximo marco

```text
RAG-003-A — Chunking de Markdown
```

O próximo marco começa a transformar fontes documentais autorizadas em chunks

Não iniciar SQLite FTS5 embeddings ou modelos antes do fechamento do RAG-003
