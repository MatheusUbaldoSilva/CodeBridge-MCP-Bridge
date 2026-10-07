# RAG-006-F — CPU fallback

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Provar funcionamento do modelo textual sem GPU e implementar fallback automático de GPU para CPU

## Device contract do llama.cpp

O binário real em

`C:\llama\llama-server.exe`

foi consultado diretamente

O help confirmou

```text
--device <dev1,dev2,..>
none = don't use offload device

-ngl / --gpu-layers N
max number of layers to store in VRAM
```

A listagem real de devices retornou

```text
Available devices:
CUDA0: NVIDIA GeForce RTX 3050 6GB Laptop GPU
```

Portanto os modos desta fase ficam explícitos

GPU

```text
--device CUDA0
-ngl 99
```

CPU puro

```text
--device none
-ngl 0
```

O identificador CUDA0 é evidência do ambiente atual

O runtime de produção não deve hardcode esse nome

Ele usa `--list-devices` para descoberta explícita

## Prova CPU real antes da implementação

O GGUF real do RAG-006-B foi iniciado com

```text
--device none
-ngl 0
--embedding
--pooling last
--host 127.0.0.1
--port 19106
```

PID

`5988`

Health

```text
HTTP/1.1 200 OK
{"status":"ok"}
```

A lista de compute processes do nvidia-smi durante essa execução mostrou outros PIDs mas não o PID 5988

Isso prova que o processo CPU não apareceu como workload de compute NVIDIA

Embedding real em CPU

```text
DIM=1024
NORM=1.000000011
```

O processo foi encerrado explicitamente ao final

## Descoberta de GPU

Criado

`discover_llama_devices`

Ele executa explicitamente

`llama-server --list-devices`

com

- shell=False
- timeout
- captura stdout/stderr

Nenhuma descoberta ocorre no import

## Configuração CPU

`build_cpu_fallback_config`

congela

```text
device = none
gpu_layers = 0
```

Uma configuração com device none e gpu_layers maior que zero é rejeitada

## Configuração GPU

`build_gpu_config`

exige device explícito diferente de none

O número de layers é no mínimo 1

Isso evita marcar uma carga silenciosamente CPU como GPU

## Fallback manager

Criado

`TextModelFallbackManager`

Fluxo

```text
descobrir devices
↓
GPU encontrada?
├── NÃO
│   ↓
│   carregar CPU direto
│
└── SIM
    ↓
    carregar GPU explícita
    ├── READY
    │   ↓
    │   usar GPU
    │
    └── ModelLoadError
        ↓
        registrar erro GPU
        ↓
        carregar CPU
```

Se CPU também falhar

`ModelFallbackExhaustedError`

preserva

- erro GPU
- erro CPU

## Estado ativo

O manager expõe

- execution_mode GPU ou CPU
- fallback_used
- gpu_error
- selected_gpu_device
- snapshot do lifecycle
- active_lifecycle

O `TextEmbeddingClient` continua recebendo o lifecycle ativo

Assim o contrato de embedding do RAG-006-D não é duplicado

## Lifecycle

IDLE READY e unload são delegados ao lifecycle realmente ativo

Após unload

- active lifecycle é removido
- execution_mode volta a None
- processo é encerrado pela política já provada no RAG-006-C

## Fronteira

RAG-006-F não mede desempenho

Não congela

- cold start
- warm query
- embeddings/s
- RAM
- VRAM
- tempo de unload

Essas métricas pertencem ao RAG-006-G

## Implementação

Atualizado

`rag/models/lifecycle.py`

Criado

`rag/models/fallback.py`

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_text_cpu_fallback.py`

## Critério de aceitação

RAG-006-F está concluído quando

- CPU puro é provado com o modelo real
- GPU usa device explícito
- ausência de GPU vai direto para CPU
- falha de carga GPU refaz a carga em CPU
- GPU success não inicia CPU
- falha dupla preserva os dois erros
- embedding real funciona em CPU
- fallback real forçado funciona
- unload final não deixa processo órfão
- suíte RAG passa
- diff check passa


## Smoke real do caminho GPU

O manager automático foi executado com o ambiente real

Resultado

```text
MODE=GPU
DEVICE=CUDA0
FALLBACK=False
PID=13068
DIM=1024
NORM=1.000000009
UNLOAD=UNLOADED
```

Isso prova que

- `--list-devices` descobriu CUDA0
- o manager selecionou GPU explicitamente
- não houve fallback quando a GPU funcionou
- o embedding real manteve dimensão 1024 e norma unitária
- unload retornou ao estado UNLOADED

O PID é somente o valor dessa execução de teste

## Smoke real do fallback automático

Para provar a troca automática foi construído um runtime com device GPU propositalmente inexistente

`CUDA_DOES_NOT_EXIST`

A tentativa GPU produziu `ModelLoadError`

O manager registrou o erro e iniciou a configuração CPU

```text
--device none
-ngl 0
```

A execução foi gravada em arquivo local para não depender do transporte do terminal

Resultado

```text
MODE=CPU
FALLBACK=True
GPU_ERROR_PRESENT=True
PID=13976
DIM=1024
NORM=0.999999978
UNLOAD=UNLOADED
```

Portanto a falha GPU não interrompeu o fluxo

O mesmo contrato de embedding continuou funcionando em CPU sem ação manual do usuário

A tentativa de uma checagem adicional via tasklist foi bloqueada pela camada de segurança da ferramenta antes de executar

A prova de encerramento desta execução é o retorno do lifecycle

`UNLOAD=UNLOADED`

somado à política de unload já validada no RAG-006-C

## Validação final

Testes específicos de fallback + lifecycle

```text
Ran 27 tests
OK
```

Suíte RAG completa

```text
Ran 326 tests
OK
```

Git whitespace audit

```text
git diff --check 772ce96bcc2161c3c182d2c8a3666db9f5f28006..HEAD
exit_code = 0
```

Worktree de validação

```text
## HEAD (no branch)
```

sem alterações locais

## Estado final do RAG-006-F

- CPU puro provado com modelo real
- CPU não apareceu como workload do PID no nvidia-smi
- embedding CPU 1024D provado
- descoberta de device implementada
- GPU explícita provada com CUDA0
- fallback automático GPU → CPU provado
- erro GPU preservado
- embedding continuou após fallback
- unload retornou UNLOADED
- 326 testes RAG passaram
- diff check passou
- nenhuma métrica de benchmark foi antecipada

RAG-006-F está pronto para fechamento
