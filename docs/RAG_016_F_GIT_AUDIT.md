# RAG-016-F — Auditoria Git formal

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Executar a política normal de fechamento antes do handoff final

Sequência exigida pelo handoff

```text
git status
git diff
revisão
testes
git diff --check
commit
push
auditoria pós-commit
working tree limpo
```

## Estado inicial da auditoria

```text
## rag-016-production...origin/rag-016-production
```

Nenhum arquivo unstaged ou untracked estava presente antes da auditoria RAG-016-F

A branch estava sincronizada com o remoto após RAG-016-E

## Base auditada

Base

`origin/rag-015-security`

HEAD antes deste documento

`6b7a634 test(rag-016-e): keep executor alive on model failure`

Quantidade de commits RAG-016 A-E

`5`

## Commits preservados

```text
7e524d0 test(rag-016-a): soak repeated indexing and retrieval
b29ee3a test(rag-016-b): prove restart recovery
1a54d5c test(rag-016-c): prove cpu-only production canary
1a361cb test(rag-016-d): prove compatible gpu canary
6b7a634 test(rag-016-e): keep executor alive on model failure
```

Cada subfase foi testada commitada e enviada separadamente

## Diff do marco A-E

Comparação

`origin/rag-015-security...HEAD`

Resultado

```text
29 files changed
3488 insertions
0 deletions
```

O marco adiciona principalmente

- harnesses de benchmark/canary
- evidências JSON
- testes
- documentação
- exports em rag/benchmark/__init__.py

Não houve remoção de implementação anterior

## Name-status

A auditoria mostrou

- 28 arquivos adicionados
- 1 arquivo modificado
- 0 arquivos deletados

Arquivo modificado

`rag/benchmark/__init__.py`

Mudança

exportar as novas APIs de benchmark/canary do RAG-016

## Revisão estrutural

RAG-016-A

- soak usa storage temporário
- não promove índice para produção
- indexação repetida precisa manter counts estáveis
- upserts vetoriais usam IDs determinísticos
- ranking idêntico precisa permanecer estável

RAG-016-B

- restart probe persiste SQLite Qdrant e baseline
- verify abre o storage novamente
- restart real gerou novos PIDs
- CodeBridge retornou READY
- retrieval pós-restart ficou idêntico

RAG-016-C

- CPU força device none
- CPU força gpu_layers 0
- Text e Code rodam sequencialmente
- ausência de nvidia-smi não quebra o caminho
- nenhum llama-server fica órfão

RAG-016-D

- GPU é descoberta por llama.cpp
- device selecionado explicitamente
- gpu_layers maior que zero
- Text e Code aparecem como NVIDIA compute
- VRAM aumenta no load e retorna ao baseline no unload
- modelos continuam sequenciais

RAG-016-E

- falhas são deliberadas com artifacts inexistentes
- artifacts reais não são alterados
- lifecycles retornam UNLOADED
- nenhuma falha deixa processo de modelo
- executor MCP permanece READY
- novo comando termina FINISHED com exit code 0

## Regra de independência do executor

A revisão confirmou que os novos módulos vivem em

`rag/benchmark/`

Nenhum deles foi adicionado ao bootstrap obrigatório do executor MCP

Isso preserva a regra permanente

`Nenhum modelo pode ser requisito para o executor MCP funcionar`

## Diff check do intervalo

Executado

`git diff --check origin/rag-015-security...HEAD`

Resultado

`OK`

Nenhum whitespace error foi encontrado no intervalo A-E

## Testes antes do fechamento

A última suíte completa executada após RAG-016-E retornou

```text
Ran 688 tests
OK
```

RAG-016-F executará novamente a suíte completa depois da criação deste documento antes do commit

## Segurança de working tree

Antes deste documento

```text
working tree clean
origin/rag-016-production...HEAD = 0 0
```

Não existe alteração pendente herdada das subfases A-E

## Critério de aceitação

RAG-016-F está concluído quando

- status é auditado
- branch base é identificada
- commits A-E são enumerados
- diff stat é auditado
- name-status é auditado
- revisão estrutural é registrada
- suíte RAG completa passa novamente
- git diff --check passa
- documento F é commitado
- commit é enviado ao origin
- auditoria pós-commit confirma sync 0/0
- working tree termina limpo

## Próximo passo

`RAG-016-G — Handoff pós-RAG`

O handoff final deve congelar arquitetura modelos hashes backends benchmarks limitações rollback e commits preservados
