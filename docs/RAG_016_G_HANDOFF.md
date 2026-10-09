# HANDOFF PÓS-RAG — CodeBridge 2.0

Data 2026-10-08

Marco

`RAG-016-G — Handoff pós-RAG`

Branch

`rag-016-production`

Base preservada anterior ao RAG-016

`010f8a2 docs(rag-015): close security milestone`

## Estado executivo

A implementação e a qualificação operacional planejadas em RAG-001 até RAG-016 foram concluídas

O RAG local possui

- inventário e políticas de fonte
- chunking determinístico
- proveniência
- SQLite + FTS5
- Jina Text
- Jina Code
- Qdrant Local
- roteamento determinístico
- busca híbrida
- RRF
- deduplicação
- staleness
- indexação incremental
- ferramentas MCP
- benchmark próprio
- segurança
- soak
- restart
- CPU-only canary
- GPU canary
- isolamento de falha dos modelos

Porém

`PRODUCTION READINESS = BLOCKED`

O marco operacional RAG-016 estar concluído não autoriza go-live enquanto o gate congelado em RAG-014-D não passar

## Regra arquitetural central

```text
RAG descobre
↓
CodeBridge verifica a fonte real
↓
arquivo/Git provam o estado atual
↓
IA decide
↓
executor MCP executa somente ação explicitamente autorizada
```

O RAG não é authority sobre arquivos nem sobre execução

Ele é camada local de descoberta e contexto

## Arquitetura congelada

```text
fontes do projeto
│
├── documentos
├── código/config
├── Git
└── execution ledger RAW por referência
    │
    ▼
source discovery
    │
    ├── denylist por path
    ├── root boundary
    ├── allowlists
    └── secret content scan
    │
    ▼
chunking determinístico
    │
    └── proveniência obrigatória
        project_id
        source_type
        path
        lines
        sha256
        indexed_at
        source_id opcional
    │
    ├─────────────────────────────┐
    ▼                             ▼
SQLite + FTS5                 embeddings
lexical/BM25                 ├── Jina Text 1024D
                             └── Jina Code 1536D
                                  │
                                  ▼
                             Qdrant Local
                             namespaces por projeto
    │                             │
    └──────────────┬──────────────┘
                   ▼
        classificador determinístico
                   │
             TEXT / CODE / HYBRID
                   │
                   ▼
              candidatos
                   │
                   ▼
               RRF k=60
                   │
                   ▼
               dedup
                   │
                   ▼
              top results
                   │
                   ▼
              get_context
                   │
          revalidação de scope
                   │
                   ▼
            fonte real / Git
```

## Executor MCP permanece independente

Regra permanente

`Nenhum modelo pode ser requisito para o executor MCP funcionar`

RAG-016-E provou essa regra em execução real

Text e Code falharam deliberadamente

Mesmo assim

```text
CodeBridge overall = READY
api_online = true
executor.running = true
PowerShell online = true
CMD online = true
SSH online = true
```

Um novo comando PowerShell depois das falhas terminou

```text
state = FINISHED
exit_code = 0
output = RAG016E_EXECUTOR_AFTER_OK
```

## Backend de inferência

Selecionado

`llama.cpp HTTP local`

Binário qualificado no host atual

`C:\llama\llama-server.exe`

Versão observada

```text
0.4.0-dev
build 10819
commit 6a1a922d2
```

Python do ambiente de desenvolvimento

`Python 3.13.15`

O servidor de modelos deve permanecer bindado em

`127.0.0.1`

## Modelo Text

Família

`jinaai/jina-embeddings-v5-text-small`

Repositório do artifact

`jinaai/jina-embeddings-v5-text-small-retrieval`

Artifact

`v5-small-retrieval-Q4_K_M.gguf`

Revision pin

`e9137ac0a9d41c851de69bea36babc029b7f5fc9`

Quantização

`Q4_K_M`

Tamanho

`396705152 bytes`

SHA-256 congelado

`9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21`

SHA-256 do arquivo instalado foi recalculado em 2026-10-08 e coincide exatamente com o pin

Dimensão

`1024`

Pooling

`last`

Prefixes

```text
Query:
Document:
```

## Modelo Code

Família

`jinaai/jina-code-embeddings-1.5b`

Artifact repository

`jinaai/jina-code-embeddings-1.5b-GGUF`

Base model

`Qwen/Qwen2.5-Coder-1.5B`

Artifact

`jina-code-embeddings-1.5b-Q8_0.gguf`

Revision pin

`67f160ae7d22bb80dc6273cedcc67c027f430c9d`

Quantização

`Q8_0`

Tamanho

`1646569888 bytes`

SHA-256 congelado

`3a09a8817b852b5a4faaa6ebb1a5590322746d2b570b578d0b7e3b6e849062aa`

SHA-256 do arquivo instalado foi recalculado em 2026-10-08 e coincide exatamente com o pin

Dimensão validada no backend atual

`1536`

Contexto recomendado

`8192 tokens`

ubatch recomendado

`8192`

Tasks contratadas incluem

- NL2CODE
- QA
- CODE2CODE
- CODE2NL
- CODE2COMPLETION

## Licença dos modelos

Ambos os policies registram

`CC-BY-NC-4.0`

e

`commercial_license_review_required = true`

Portanto um uso comercial não deve ser declarado liberado apenas porque os modelos funcionam tecnicamente

A licença precisa ser revisada ou substituída por modelo/artifact com termos compatíveis antes de um go-live comercial

## Download e distribuição

`auto_download_allowed = false`

`download_allowed = false`

Os artifacts não podem ser baixados silenciosamente pelo runtime

O fluxo de instalação/download precisa continuar explícito e auditável

A policy prevê sidecar distribuível

O host de qualificação atual usa

`C:\llama\llama-server.exe`

A embalagem final do sidecar no instalador precisa ser validada separadamente antes de distribuição ampla

## Política de residência de modelos

Regra congelada

`não manter ambos os modelos residentes sem benchmark que justifique`

Fluxo atual

```text
classificar query
↓
carregar modelo necessário
↓
embedding/retrieval
↓
idle/unload
↓
trocar somente quando necessário
```

CPU e GPU canaries executam Text e Code sequencialmente

## CPU fallback

Contrato

```text
--device none
-ngl 0
```

RAG-016-C real

Text

```text
dimension = 1024
norm = 1.000000038
load = 9.150 s
embedding = 271.250 ms
working set ≈ 4.43 GiB
NVIDIA compute = false
```

Code

```text
dimension = 1536
norm = 0.999999980
load = 4.682 s
embedding = 252.517 ms
working set ≈ 2.00 GiB
NVIDIA compute = false
```

Nenhum llama-server permaneceu após unload

Limitação

o host físico usado possui RTX 3050

O CPU-only foi provado desabilitando explicitamente todo offload

Ainda é recomendado canary adicional em máquina fisicamente sem GPU dedicada antes de distribuição geral

## GPU canary

Device descoberto dinamicamente

`CUDA0`

Contrato observado

```text
--device CUDA0
-ngl 99
```

Text

```text
dimension = 1024
norm = 1.000000036
load = 1.920 s
embedding = 117.823 ms
VRAM 160 → 4375 → 160 MiB
delta = 4215 MiB
NVIDIA compute = true
```

Code

```text
dimension = 1536
norm = 1.000000028
load = 2.980 s
embedding = 104.175 ms
VRAM 160 → 3277 → 160 MiB
delta = 3117 MiB
NVIDIA compute = true
```

## Benchmark de qualidade RAG-014

Dataset

`100 queries`

Ground truth

manual e versionado

Resultado semântico real

```text
Recall@5  = 0.46
Recall@10 = 0.48
MRR       = 0.3257777778
```

Latência

```text
cold estimate ≈ 3271.871 ms
warm mean ≈ 87.957 ms
warm p95 ≈ 140.112 ms
```

Recursos

```text
llama peak RSS = 4947095552 bytes
max VRAM delta = 4215 MiB
index total = 90600481 bytes
```

## Gate de go-live

Thresholds congelados

```text
Recall@5  >= 0.80
Recall@10 >= 0.90
MRR       >= 0.60
cold      <= 20000 ms
warm p95  <= 1000 ms
RAM       <= 6 GiB
VRAM      <= 5120 MiB
index     <= 2 GiB
production index must be READY
```

Estado atual

`BLOCKED`

Falhas atuais

```text
production_index:NOT_READY
recall_at_5:BELOW_THRESHOLD:0.460000<0.800000
recall_at_10:BELOW_THRESHOLD:0.480000<0.900000
mrr:BELOW_THRESHOLD:0.325778<0.600000
```

Latência RAM VRAM e tamanho do índice passaram

Não reduzir thresholds para transformar o resultado em PASS

## RAG-016-A — Soak

Commit

`7e524d0`

Execução real

```text
10 index cycles
1000 query cycles
188 documents no snapshot
7527 chunks no snapshot
text vector points = 1
code vector points = 1
elapsed = 344.047 s
RSS delta ≈ 64.7 MiB
temporary index ≈ 15.15 MiB
```

Counts e ranking permaneceram estáveis

## RAG-016-B — Restart

Commit

`b29ee3a`

Antes

```text
author MCP PID 2752
executor PID 2328
main PID 1720
```

Depois

```text
author MCP PID 9612
executor PID 12340
main PID 12452
```

O CodeBridge retornou READY

O executor executou comando real com exit code 0

O índice persistente de probe recuperou exatamente

```text
190 documents
7639 chunks
1 text vector
1 code vector
mesma assinatura de 8 chunks
```

## RAG-016-C — CPU-only

Commit

`1a54d5c`

Canary consolidado dos dois modelos em CPU puro

## RAG-016-D — GPU

Commit

`1a361cb`

Canary consolidado dos dois modelos em GPU explícita

## RAG-016-E — Falha do modelo

Commit

`6b7a634`

Text e Code falharam propositalmente

Executor MCP permaneceu operacional

## RAG-016-F — Auditoria Git

Commit

`ad5768d`

Antes de F

```text
29 files changed
3488 insertions
0 deletions
5 commits A-E
range diff check OK
working tree clean
sync 0 0
```

Depois de F

```text
688 tests
OK
push OK
working tree clean
sync 0 0
```

## Segurança congelada no RAG-015

Secrets

- denylist por path
- detecção por conteúdo
- findings sem raw secret

Scope

- SQLite por project_id
- Qdrant por project_namespace
- get_context revalida projeto

Path traversal

- POSIX
- Windows
- absoluto externo
- revalidação em retrieval e Git

Origem

- chunk precisa de provenance mínima verificável

Exclusão

- derived data pode ser removido por namespace
- arquivos fonte permanecem intocados

## Índice incremental

Regra

`não reindexar arquivo cujo conteúdo não mudou`

O manifest persiste identidade de arquivo/chunks/model version

Mudança de conteúdo reindexa somente a fonte afetada

Mudança de model version invalida somente o índice correspondente

Arquivos removidos eliminam chunks órfãos

## Git e staleness

Git continua sendo prova de versão

Resultados carregam metadados que permitem detectar fonte stale

Antes de alteração real

`reler/verificar a fonte real`

RAG não substitui essa etapa

## RAW / execution ledger

Regra permanente

`RAW continua recuperável pelo ledger e não é duplicado no RAG`

O benchmark corrigiu ground truths que apontavam somente para RAW inelegível

Nenhuma mudança posterior deve relaxar essa fronteira sem nova revisão de segurança

## Testes

Última suíte completa antes do handoff

```text
Ran 688 tests
OK
```

O conjunto cobre desde contratos RAG iniciais até segurança e produção

## Milestone closeouts preservados

```text
RAG-001  2ecaca2
RAG-002  30f1615
RAG-003  0d0b7e6
RAG-004  58eaced
RAG-005  c27312e
RAG-006  4452e22
RAG-007  43228b4
RAG-008  d16be9b
RAG-009  4dc62b5
RAG-010  f0dd57c
RAG-011  d184ca0
RAG-012  fdf7d1d
RAG-013  6c1a419
RAG-014  e969fb6
RAG-015  010f8a2
```

## RAG-016 commits preservados

```text
7e524d0 RAG-016-A soak
b29ee3a RAG-016-B restart
1a54d5c RAG-016-C CPU-only
1a361cb RAG-016-D GPU
6b7a634 RAG-016-E model failure isolation
ad5768d RAG-016-F Git audit
```

O commit do próprio RAG-016-G deve ser preservado como último commit deste marco

## Rollback

### Regra

Não usar reset destrutivo em branch compartilhada

Não apagar history remoto

### Checkpoint anterior ao RAG-016

`010f8a2`

Esse commit representa o fechamento RAG-015 antes de qualquer alteração de produção qualification RAG-016

### Rollback seguro por Git

Criar branch dedicada a partir do estado atual

```text
git switch -c rollback/rag-016
```

Reverter os commits RAG-016 em ordem inversa usando `git revert`

Após o commit do handoff G

1. revert do commit RAG-016-G
2. `ad5768d`
3. `6b7a634`
4. `1a361cb`
5. `1a54d5c`
6. `b29ee3a`
7. `7e524d0`

Validar testes e diff antes de push

### Rollback operacional sem Git

Os modelos não são requisito para o executor

Portanto em incidente de RAG

- não iniciar modelos
- manter executor MCP ativo
- usar o caminho sem RAG
- preservar artifacts e índices para auditoria

### Índices

RAG-016 usa probes temporários e não promove índice persistente para produção

Para derived data de projeto que precise ser removido

usar a API namespace-scoped criada em RAG-015-E

`delete_project_index()`

Nunca apagar source files como parte de rollback do RAG

## Limitações e pendências antes de go-live

1. Recall@5 abaixo do threshold

2. Recall@10 abaixo do threshold

3. MRR abaixo do threshold

4. production index ainda não READY

5. licença CC-BY-NC-4.0 exige revisão para uso comercial

6. CPU-only ainda deve ser repetido em hardware fisicamente sem GPU para canary de distribuição

7. packaging do llama.cpp sidecar precisa ser validado no instalador final

8. modelos não podem ser auto-downloaded silenciosamente

9. ambos os modelos não devem ficar residentes simultaneamente sem novo benchmark

10. qualquer mudança de modelo exige novo pin hash benchmark e avaliação do gate

## Próxima ação técnica correta

Não adicionar novas features RAG antes de resolver o gate de qualidade

A próxima frente deve ser melhoria mensurável de retrieval contra o dataset congelado do RAG-014

Objetivo

```text
Recall@5  >= 0.80
Recall@10 >= 0.90
MRR       >= 0.60
```

sem relaxar segurança e sem reduzir thresholds

Depois

- construir índice persistente real
- obter estado READY
- repetir benchmark
- repetir segurança/canaries relevantes
- revisar licença comercial
- somente então reconsiderar go-live

## Estado final deste handoff

`RAG-016-G ✅ HANDOFF GERADO`

`RAG-001 → RAG-016 implementação e qualificação operacional concluídas`

`GO-LIVE RAG = BLOQUEADO pelo gate RAG-014`

Essa distinção deve permanecer explícita em qualquer continuação futura
