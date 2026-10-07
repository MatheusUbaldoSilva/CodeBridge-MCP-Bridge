# RAG-006 — Closeout do modelo textual Jina v5

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Estado

`RAG-006 ✅ FECHADO`

O critério do handoff foi cumprido

O modelo textual está selecionado, pinado, instalado, carregado sob demanda, capaz de gerar embeddings, reutilizar cache, operar com fallback CPU e possui benchmark real registrado

## Sequência fechada

### RAG-006-A — Backend

Commit

`d61d279a92d839fa402f5f254a8f13ac13ee7bf0`

Resultado

- backend selecionado: llama.cpp HTTP local
- sidecar fora do runtime Python principal
- GPU preferida
- CPU fallback obrigatório
- endpoint `/v1/embeddings`
- pooling `last`
- download automático desligado
- bundling desligado
- revisão comercial de licença obrigatória

### RAG-006-B — Download e instalação controlada

Commit

`7264a6a7846d5eb29e6270daafccc87d23bbcf38`

Artefato congelado

```text
repository=jinaai/jina-embeddings-v5-text-small-retrieval
revision=e9137ac0a9d41c851de69bea36babc029b7f5fc9
filename=v5-small-retrieval-Q4_K_M.gguf
quantization=Q4_K_M
size_bytes=396705152
sha256=9440cf89f3e8a7a31a42e11b87e106dd5b344af4e0e3b6b21a96136cc8686e21
license=CC-BY-NC-4.0
```

Instalação real validada

- tamanho exato confirmado
- SHA-256 confirmado
- instalação atômica
- arquivo parcial não é promovido sem validação
- download exige autorização explícita
- licença exige acknowledgement explícito

## RAG-006-C — Lifecycle sob demanda

Commit

`81517d04fbb7c324d8770aee4c59d38c3fae813d`

State machine

```text
UNLOADED
→ LOADING
→ READY
→ IDLE
→ READY
→ UNLOADING
→ UNLOADED
```

Provas reais

- health gate HTTP 200
- PID conhecido
- porta local automática
- load idempotente
- unload real
- nenhum processo órfão no smoke validado

## RAG-006-D — Embedding textual

Commit

`6e7c73f1b2914b458bdf92bf9387d453a4931605`

Contrato congelado

```text
dimension=1024
query_prefix="Query: "
document_prefix="Document: "
norm_target=1.0
norm_tolerance=1e-3
repeatability_min_cosine=0.9999
batch_size=1
```

Corpus textual permitido

- DOCUMENTATION
- AUDIT
- LOG
- GIT
- EXECUTION

`CODE` não é indexado pelo modelo textual

Código-fonte permanece reservado ao RAG-007

## RAG-006-E — Cache

Commit

`772ce96bcc2161c3c182d2c8a3666db9f5f28006`

Cache

- SQLite dedicado
- separado do FTS5
- chave por namespace do modelo + SHA-256 do conteúdo do chunk
- vetor float64
- SHA-256 próprio do BLOB
- corrupção gera erro explícito
- hit funciona com modelo UNLOADED
- chunks diferentes com conteúdo idêntico reutilizam vetor

Nenhum vector store foi antecipado

## RAG-006-F — CPU fallback

Commit

`b8a27f16075fe1b0f98de7d91f48f30a0516b7a5`

Modos explícitos

GPU

```text
--device <device descoberto>
-ngl 99
```

CPU

```text
--device none
-ngl 0
```

Provas reais

GPU disponível

```text
MODE=GPU
DEVICE=CUDA0
FALLBACK=False
DIM=1024
NORM=1.000000009
UNLOAD=UNLOADED
```

Fallback forçado

```text
MODE=CPU
FALLBACK=True
GPU_ERROR_PRESENT=True
DIM=1024
NORM=0.999999978
UNLOAD=UNLOADED
```

CPU puro também foi validado sem workload do PID no nvidia-smi

## RAG-006-G — Benchmark

Commit

`f2717d0064d23f3623f36573c67c4b5b6b41c1de`

Metodologia versionada

- cold start: load até READY
- warm query: 1 warm-up descartado + média de 5 queries
- throughput: 20 document embeddings
- batch efetivo 1
- RAM: Working Set do PID
- VRAM: delta device-wide por limitação WDDM
- unload: tempo até UNLOADED

### GPU

```text
cold_start=1.943 s
warm_query_mean=27.94 ms
embeddings_per_second=42.05
ram_working_set=784.00 MiB
vram_delta_device_wide=4214 MiB
unload=111.36 ms
```

### CPU

```text
cold_start=6.864 s
warm_query_mean=26.42 ms
embeddings_per_second=20.59
ram_working_set=4845.20 MiB
vram_delta_device_wide=0 MiB
unload=349.91 ms
```

Comparação observada

- GPU aproximadamente 3.53 vezes mais rápida no cold start
- GPU aproximadamente 2.04 vezes maior em throughput
- GPU aproximadamente 3.14 vezes mais rápida no unload
- CPU aproximadamente 5.7 por cento mais rápida na warm query curta específica

A warm query isolada não substitui throughput como medida de capacidade sustentada

## Ambiente real validado

- Windows
- `C:\llama\llama-server.exe`
- NVIDIA GeForce RTX 3050 6GB Laptop GPU
- device descoberto no benchmark: `CUDA0`
- modelo real instalado em `%LOCALAPPDATA%\CodeBridge\models\...`

O identificador `CUDA0` não é hardcoded em produção

Ele é descoberto por `llama-server --list-devices`

## Testes

Suíte RAG final antes do closeout

```text
Ran 329 tests
OK
```

O RAG-006-G passou também por

```text
git diff --check
exit_code=0
```

## Arquitetura consolidada

Fluxo textual disponível após RAG-006

```text
fonte textual
↓
chunking + proveniência
↓
cache lookup por chunk SHA-256
├── hit
│   ↓
│   vetor validado sem carregar modelo
│
└── miss
    ↓
    GPU disponível?
    ├── sim → llama.cpp GPU
    └── não/falha → llama.cpp CPU
          ↓
       embedding 1024D
          ↓
       validação
          ↓
       cache
```

## Segurança e fronteiras

Continuam congelados

- bind local em 127.0.0.1
- download automático desligado
- bundling do modelo desligado
- revisão de licença comercial obrigatória
- SHA-256 do artefato obrigatório
- health gate obrigatório
- CPU fallback obrigatório
- cache separado do índice vetorial

## Não pertence ao RAG-006

### RAG-007

Jina Code 1.5B

- backend de código
- embedding de código
- NL → code
- code → code
- fallback CPU
- benchmark de memória

### RAG-008

Model Manager

- classificação TEXT/CODE/HYBRID/LEXICAL_ONLY
- exclusão mútua dos modelos
- idle timeout automático
- coordenação de lifecycle

### RAG-009

Índice vetorial

- Qdrant ou solução aprovada
- nearest-neighbor search
- armazenamento vetorial de produção
- ranking semântico

Esses recursos não foram antecipados neste marco

## Critério de fechamento

RAG-006 pode ser marcado fechado porque

- backend foi selecionado
- modelo exato foi pinado
- instalação real foi validada
- lifecycle real foi validado
- embeddings reais foram validados
- cache foi validado
- CPU fallback real foi validado
- benchmark GPU e CPU foi registrado
- suíte RAG está verde
- Git diff check está limpo
- nenhum escopo dos marcos seguintes foi antecipado

## Próximo marco

`RAG-007 — Jina Code 1.5B`

O primeiro passo oficial é

`RAG-007-A — Backend`

Validar compatibilidade real do modelo de código com o backend escolhido antes de baixar ou integrar qualquer artefato
