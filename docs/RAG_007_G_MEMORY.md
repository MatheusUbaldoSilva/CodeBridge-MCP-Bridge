# RAG-007-G — Memória e liberação após unload

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Provar que o Jina Code 1.5B Q8_0 libera memória suficiente após unload

Esse marco fecha o requisito do handoff

`Provar que descarregar o modelo realmente libera memória suficiente`

## Metodologia

Backend

`C:\llama\llama-server.exe`

Modelo

`jina-code-embeddings-1.5b-Q8_0.gguf`

Cada modo executou

1. captura de RAM livre e VRAM antes da carga
2. início real do llama-server
3. espera do health `ok`
4. uma consulta NL→code real
5. captura do Working Set do PID
6. captura de RAM livre e VRAM com o modelo carregado
7. encerramento do processo
8. espera de 1 segundo para estabilização
9. nova captura de RAM livre e VRAM
10. confirmação de que o PID deixou de existir

A consulta real produziu embedding de 1536 dimensões nos dois modos

## Critério de liberação

GPU

- processo deve desaparecer
- VRAM deve retornar ao baseline ou ficar dentro de pequena margem operacional

CPU

- processo deve desaparecer
- RAM livre deve retornar próxima ao baseline
- diferença residual pequena é tratada como ruído normal do sistema operacional e processos concorrentes

Para esta validação foi usada margem prática de 64 MiB para RAM livre do host

## Resultado real — GPU

Configuração

```text
--device CUDA0
-ngl 99
```

Resultado

```text
PID=7416
DIM=1536
QUERY_MS=131.390
RAM_WS_BYTES=2107711488
FREE_RAM_BEFORE_BYTES=901079040
FREE_RAM_LOADED_BYTES=522592256
FREE_RAM_AFTER_BYTES=881438720
FREE_RAM_DROP_BYTES=378486784
FREE_RAM_RECOVERED_BYTES=358846464
VRAM_BEFORE_MIB=157
VRAM_LOADED_MIB=3274
VRAM_AFTER_MIB=157
VRAM_LOAD_DELTA_MIB=3117
VRAM_RELEASED_MIB=3117
UNLOAD_MS=9.297
PROCESS_ALIVE=False
```

Interpretação

- o processo terminou
- a VRAM subiu 3117 MiB durante a carga
- após unload a VRAM voltou exatamente de 3274 MiB para 157 MiB
- os 3117 MiB adicionados pelo modelo foram liberados
- a RAM livre após unload ficou apenas 19640320 bytes abaixo do valor anterior à carga
- diferença residual de RAM ≈ 18.73 MiB
- essa diferença fica dentro da margem de 64 MiB

## Resultado real — CPU

Configuração

```text
--device none
-ngl 0
```

Resultado

```text
PID=12944
DIM=1536
QUERY_MS=345.833
RAM_WS_BYTES=212312064
FREE_RAM_BEFORE_BYTES=933634048
FREE_RAM_LOADED_BYTES=774328320
FREE_RAM_AFTER_BYTES=893386752
FREE_RAM_DROP_BYTES=159305728
FREE_RAM_RECOVERED_BYTES=119058432
VRAM_BEFORE_MIB=157
VRAM_LOADED_MIB=157
VRAM_AFTER_MIB=157
UNLOAD_MS=10.732
PROCESS_ALIVE=False
```

Interpretação

- o processo terminou
- CPU puro não adicionou VRAM
- VRAM permaneceu 157 MiB antes durante e depois
- a RAM livre após unload ficou 40247296 bytes abaixo do valor anterior à carga
- diferença residual de RAM ≈ 38.38 MiB
- essa diferença fica dentro da margem de 64 MiB

## Observações sobre memória

O Working Set do processo não deve ser interpretado isoladamente como memória física exclusiva do modelo

O llama.cpp usa arquivos mapeados e o Windows pode contabilizar cache e páginas compartilhadas de forma diferente do Working Set

Por isso a prova de liberação usa conjuntamente

- desaparecimento do PID
- RAM livre antes e depois
- VRAM device-wide antes e depois
- unload medido

## Resultado do critério

GPU

`PASS`

CPU

`PASS`

Nos dois modos o processo foi encerrado e os recursos retornaram ao sistema em nível suficiente para o ciclo sob demanda do CodeBridge 2.0

## Estado do RAG-007

RAG-007-A ✅ backend

RAG-007-B ✅ lifecycle

RAG-007-C ✅ embeddings

RAG-007-D ✅ NL→code

RAG-007-E ✅ code→code

RAG-007-F ✅ CPU fallback e latência

RAG-007-G ✅ memória e unload

Pelo critério do handoff o RAG-007 está pronto para closeout formal após auditoria Git testes diff check commit e auditoria pós-commit
