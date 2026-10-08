# RAG-016-D — Canary GPU compatível

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Executar o canary de produção em uma GPU compatível com offload explícito e preservar o fallback CPU já validado

Requisito do handoff

`Canary com GPU compatível`

## Descoberta de device

O canary não hardcodeia a GPU como requisito de arquitetura

Ele chama

`discover_llama_devices()`

contra o binário real

`C:\llama\llama-server.exe`

Resultado observado

```text
discovered_devices = [CUDA0]
selected_device = CUDA0
```

O host atual possui

`NVIDIA GeForce RTX 3050 6GB Laptop GPU`

## Contrato GPU

Os dois modelos são carregados sequencialmente com

```text
--device CUDA0
-ngl 99
```

A configuração passa por `build_gpu_config()`

Logo

- device precisa ser explícito
- device não pode ser none
- gpu_layers precisa ser pelo menos 1

## Text model

Modelo

`jina-v5-text-small-retrieval`

Resultado real

```text
device = CUDA0
gpu_layers = 99
pid = 10012
dimension = 1024
norm = 1.0000000362747592
load_seconds = 1.9196748
embedding_ms = 117.8227
unload_ms = 91.6568
working_set_bytes = 839483392
nvidia_compute_present = true
```

VRAM

```text
before = 160 MiB
loaded = 4375 MiB
after unload = 160 MiB
delta = 4215 MiB
```

O processo foi observado explicitamente na lista NVIDIA compute

## Code model

Modelo

`jina-code-embeddings-1.5b`

Consulta real

`NL2CODE`

Resultado

```text
device = CUDA0
gpu_layers = 99
pid = 12896
dimension = 1536
norm = 1.0000000277464334
load_seconds = 2.9798464
embedding_ms = 104.1746
unload_ms = 211.2354
working_set_bytes = 2109947904
nvidia_compute_present = true
```

VRAM

```text
before = 160 MiB
loaded = 3277 MiB
after unload = 160 MiB
delta = 3117 MiB
```

## Residência sequencial

O canary mantém a regra arquitetural já congelada

`não manter ambos os modelos residentes sem benchmark que justifique`

Fluxo

```text
Text GPU
↓ embedding
↓ unload
Code GPU
↓ embedding
↓ unload
```

Assim o pico de VRAM não é a soma dos dois modelos

## Liberação de memória

Nos dois casos a VRAM voltou exatamente ao baseline observado

```text
Text 4375 → 160 MiB
Code 3277 → 160 MiB
```

Depois do canary foi feita auditoria de processo

Nenhum `llama-server` permaneceu ativo

## Implementação

Criado

`rag/benchmark/gpu_canary.py`

API

`run_gpu_canary()`

O canary mede

- device descoberto
- device selecionado
- gpu_layers
- PID
- dimensão
- norma
- load
- embedding
- unload
- working set
- presença NVIDIA compute
- VRAM baseline
- VRAM loaded
- VRAM after unload
- VRAM delta

## Evidência

Runner

`benchmarks/run_rag016_gpu_canary.py`

Resultado

`benchmarks/rag016_gpu_canary_latest.json`

## Testes

Criado

`tests/test_rag_016_gpu_canary.py`

Casos

- configuração GPU exige device explícito
- offload é maior que zero
- cálculo de delta de VRAM
- contrato congela execution_mode GPU
- ausência de GPU compatível falha antes de carregar modelo

Resultado focado

```text
Ran 4 tests
OK
```

## Relação com CPU-only

RAG-016-C continua intacto

O caminho GPU não substitui nem remove

```text
--device none
-ngl 0
```

A arquitetura continua

```text
GPU compatível
↓ preferida

falha/ausência de GPU
↓
CPU fallback
```

## Critério de aceitação

RAG-016-D está concluído quando

- device compatível é descoberto
- GPU é selecionada explicitamente
- Text embedding real é válido
- Code embedding real é válido
- ambos aparecem como NVIDIA compute
- uso de VRAM aumenta durante load
- VRAM retorna ao baseline após unload
- nenhum llama-server fica órfão
- CPU fallback permanece disponível
- testes passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-016-E — Falha do modelo`

Provar que uma falha deliberada de modelo não derruba o executor MCP
