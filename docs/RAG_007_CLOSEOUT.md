# RAG-007 — Closeout do Jina Code 1.5B

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Estado

`RAG-007 ✅ FECHADO`

O critério do handoff foi cumprido

O modelo de código está pinado carregável sob demanda capaz de gerar embeddings task-aware recuperar NL→code e code→code operar em CPU puro e liberar memória após unload

## Base

RAG-007 parte do fechamento do RAG-006

`4452e22 docs(rag-006): close Jina text embedding milestone`

## Modelo congelado

```text
family=jinaai/jina-code-embeddings-1.5b
repository=jinaai/jina-code-embeddings-1.5b-GGUF
revision=67f160ae7d22bb80dc6273cedcc67c027f430c9d
filename=jina-code-embeddings-1.5b-Q8_0.gguf
quantization=Q8_0
size_bytes=1646569888
sha256=3a09a8817b852b5a4faaa6ebb1a5590322746d2b570b578d0b7e3b6e849062aa
license=CC-BY-NC-4.0
dimension=1536
```

Download automático continua desligado

Bundling do modelo continua desligado

Revisão comercial da licença continua obrigatória

## RAG-007-A — Backend

Commit

`7e59a1b feat(rag-007-a): validate Jina code backend`

Resultado

- backend llama.cpp HTTP local validado
- endpoint de embeddings local
- pooling last
- GPU preferida
- CPU fallback obrigatório
- dimensão de referência 1536
- contexto máximo registrado em 32768 tokens
- contexto recomendado 8192
- ubatch recomendado 8192
- instruções task-aware congeladas

## RAG-007-B — Lifecycle

Commit

`26dff71 feat(rag-007-b): pin and load Jina code model`

Resultado

- artefato Q8_0 pinado
- lifecycle sob demanda integrado
- health gate preservado
- modelo não é carregado no import
- log dedicado do Jina Code
- estado UNLOADED → LOADING → READY → IDLE → UNLOADING → UNLOADED preservado

## RAG-007-C — Embedding de código

Commit

`15af7a6 feat(rag-007-c): add code embedding contract`

Contrato

```text
dimension=1536
norm_target=1.0
norm_tolerance=1e-3
repeatability_min_cosine=0.9999
batch_size=1
source_type=CODE
```

Tasks usadas no corpus

- NL2CODE
- CODE2CODE

## RAG-007-D — NL → code

Commit

`e370bf8 feat(rag-007-d): add in-memory NL to code retrieval`

Resultado

- consulta em linguagem natural recebe embedding QUERY NL2CODE
- chunks de código recebem embedding PASSAGE NL2CODE
- ranking por similaridade implementado em memória
- proveniência do chunk preservada
- top-k determinístico testado

## RAG-007-E — code → code

Commit

`34f2b53 feat(rag-007-e): add in-memory code to code retrieval`

Resultado

- trecho de código recebe embedding QUERY CODE2CODE
- corpus usa embedding PASSAGE CODE2CODE
- recuperação de código equivalente validada
- ranking em memória preserva metadados e proveniência
- nenhuma vector store foi antecipada

## RAG-007-F — CPU fallback e latência

Commit

`d7980e2 docs(rag-007-f): prove CPU fallback viability`

CPU real

```text
--device none
-ngl 0
```

NL→code

```text
DIM=1536
NORM=1.000000001
FIRST_MS=330.864
WARM_MEAN_MS=56.668
```

Code→code

```text
CODE2CODE_DIM=1536
CODE2CODE_NORM=0.999999952
CODE2CODE_MS=305.629
```

O PID do runtime CPU não apareceu como workload compute NVIDIA

CPU puro foi considerado operacionalmente viável como fallback

## RAG-007-G — Memória e unload

Commit

`6bdc454 docs(rag-007-g): prove memory release after unload`

### GPU

```text
PID=7416
DIM=1536
QUERY_MS=131.390
RAM_WS_BYTES=2107711488
FREE_RAM_BEFORE_BYTES=901079040
FREE_RAM_LOADED_BYTES=522592256
FREE_RAM_AFTER_BYTES=881438720
VRAM_BEFORE_MIB=157
VRAM_LOADED_MIB=3274
VRAM_AFTER_MIB=157
VRAM_LOAD_DELTA_MIB=3117
VRAM_RELEASED_MIB=3117
UNLOAD_MS=9.297
PROCESS_ALIVE=False
```

A VRAM adicionada pelo modelo foi liberada integralmente no teste

### CPU

```text
PID=12944
DIM=1536
QUERY_MS=345.833
RAM_WS_BYTES=212312064
FREE_RAM_BEFORE_BYTES=933634048
FREE_RAM_LOADED_BYTES=774328320
FREE_RAM_AFTER_BYTES=893386752
VRAM_BEFORE_MIB=157
VRAM_LOADED_MIB=157
VRAM_AFTER_MIB=157
UNLOAD_MS=10.732
PROCESS_ALIVE=False
```

CPU não adicionou VRAM

Nos dois modos o processo desapareceu após unload

A RAM livre retornou dentro da margem prática de 64 MiB definida para ruído do host

## Testes

Suíte RAG final antes do closeout

```text
Ran 380 tests
OK
```

Auditorias

```text
git diff --check
OK
```

```text
git diff --cached --check
OK
```

## Arquitetura consolidada

Fluxo de código após RAG-007

```text
arquivo de código
↓
chunking estrutural + proveniência
↓
Jina Code 1.5B Q8_0
↓
task
├── NL2CODE
└── CODE2CODE
↓
embedding 1536D normalizado
↓
ranking em memória
↓
resultado com chunk e metadados
```

O índice vetorial ainda não existe

A busca atual de RAG-007 continua deliberadamente em memória

## Fronteiras preservadas

Não pertencem ao RAG-007

### RAG-008

Model Manager

- classificação TEXT CODE HYBRID LEXICAL_ONLY
- exclusão mútua dos modelos
- idle timeout
- coordenação de concorrência
- fallback mantendo FTS5 disponível em falha de modelo

### RAG-009

Índice vetorial

- escolha do armazenamento
- coleções text e code
- namespaces de projeto
- IDs determinísticos

### RAG-010

Busca híbrida

- FTS5 + vetor textual
- FTS5 + vetor de código
- Reciprocal Rank Fusion
- deduplicação

Esses marcos não foram antecipados

## Critério de fechamento

RAG-007 pode ser marcado fechado porque

- backend foi validado
- artefato exato foi pinado
- lifecycle sob demanda foi integrado
- embedding real 1536D foi validado
- NL→code foi validado
- code→code foi validado
- CPU puro foi validado
- latência CPU foi registrada
- memória GPU e CPU foi medida
- unload liberou recursos suficientemente
- 380 testes RAG passaram
- diff check passou
- commits de cada subfase existem
- branch foi sincronizada com origin após RAG-007-G

## Próximo marco

`RAG-008 — Model Manager sob demanda`

Primeiro passo oficial

`RAG-008-A — Classificador de consulta`

Classificar deterministicamente entre

```text
TEXT
CODE
HYBRID
LEXICAL_ONLY
```

Sem usar LLM para classificação nesta fase
