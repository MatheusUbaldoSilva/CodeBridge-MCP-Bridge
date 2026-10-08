# RAG-016-C — Canary CPU-only

Data 2026-10-08

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-016-production`

## Objetivo

Provar que o backend RAG funciona sem GPU dedicada como requisito operacional

Requisito do handoff

`Canary de instalação sem GPU dedicada`

## Contrato do canary

O canary força explicitamente llama.cpp para CPU

```text
--device none
-ngl 0
```

Os dois modelos são carregados sequencialmente

```text
Jina v5 text
↓ unload
Jina Code 1.5B
↓ unload
```

Assim não existe dependência de residência simultânea dos dois modelos

## Implementação

Criado

`rag/benchmark/cpu_canary.py`

API

`run_cpu_only_canary()`

O módulo usa os artifacts já pinados e verificados pelo projeto

Text

`jina-v5-text-small-retrieval`

Code

`jina-code-embeddings-1.5b`

Backend

`C:\llama\llama-server.exe`

## GPU não é requisito

O teste não depende de `nvidia-smi`

Se o utilitário não existir

`nvidia_compute_pids()`

retorna `None` e o CPU canary continua válido

Quando NVIDIA está presente no host atual ela é usada somente como evidência adicional

O processo CPU não pode aparecer na lista de compute PIDs

## Execução real — text model

Resultado

```text
model = jina-v5-text-small-retrieval
device = none
gpu_layers = 0
pid = 12996
dimension = 1024
norm = 1.0000000382873502
load_seconds = 9.1503443
embedding_ms = 271.2503
unload_ms = 351.0791
working_set_bytes = 4756385792
nvidia_compute_present = false
```

Working set observado

aproximadamente `4.43 GiB`

O embedding foi aceito pelo contrato de dimensão e normalização

## Execução real — code model

Resultado

```text
model = jina-code-embeddings-1.5b
device = none
gpu_layers = 0
pid = 256
dimension = 1536
norm = 0.9999999796870912
load_seconds = 4.6816116
embedding_ms = 252.5170
unload_ms = 195.2311
working_set_bytes = 2144837632
nvidia_compute_present = false
```

Working set observado

aproximadamente `2.00 GiB`

A consulta usou semântica real

`NL2CODE`

## Ausência de offload NVIDIA

No host atual existe GPU NVIDIA

Mesmo assim

```text
text nvidia_compute_present = false
code nvidia_compute_present = false
```

Isso confirma que o canary não caiu silenciosamente em GPU

A configuração observada continuou

```text
device = none
gpu_layers = 0
```

## Unload

Depois da execução foi auditada a lista de processos

Nenhum `llama-server` permaneceu ativo

Logo ambos os modelos foram descarregados ao final

## Runner

Criado

`benchmarks/run_rag016_cpu_canary.py`

Evidência gerada

`benchmarks/rag016_cpu_canary_latest.json`

## Testes automáticos

Criado

`tests/test_rag_016_cpu_canary.py`

Casos

- configuração text congela device none
- configuração text congela gpu_layers zero
- ausência de nvidia-smi não impede CPU-only
- parser de compute PIDs ignora valores inválidos
- resultado congela execution_mode CPU_ONLY

Resultado

```text
Ran 4 tests in 0.001s
OK
```

## Limite desta prova

O host físico possui uma RTX 3050

Portanto este canary prova o caminho técnico CPU-only por desativação explícita de qualquer offload

Ele não substitui um futuro teste de distribuição em uma máquina fisicamente sem GPU NVIDIA

Esse futuro teste não exige mudança de arquitetura porque o canary não depende de CUDA nem de nvidia-smi para funcionar

## Relação com RAG-006-F e RAG-007-F

RAG-006-F já havia provado CPU fallback do modelo textual

RAG-007-F já havia provado CPU fallback do modelo de código

RAG-016-C consolida os dois como canary sequencial de produção e registra uma única evidência operacional

## Arquivos

Criado

`rag/benchmark/cpu_canary.py`

Atualizado

`rag/benchmark/__init__.py`

Criado

`tests/test_rag_016_cpu_canary.py`

Criado

`benchmarks/run_rag016_cpu_canary.py`

Criado

`benchmarks/rag016_cpu_canary_latest.json`

Criado

`docs/RAG_016_C_CPU_ONLY.md`

## Critério de aceitação

RAG-016-C está concluído quando

- text model carrega com device none
- text model usa zero GPU layers
- embedding text real é válido
- text model não aparece como NVIDIA compute
- text model descarrega
- code model carrega com device none
- code model usa zero GPU layers
- embedding code real é válido
- code model não aparece como NVIDIA compute
- code model descarrega
- nenhum llama-server fica órfão
- ausência de nvidia-smi não quebra o caminho CPU-only
- testes passam
- suíte RAG passa
- git diff check passa

## Próximo passo

`RAG-016-D — GPU`

Executar canary com GPU compatível e offload explícito sem alterar o fallback CPU
