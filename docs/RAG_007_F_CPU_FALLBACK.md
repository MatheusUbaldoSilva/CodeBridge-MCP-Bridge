# RAG-007-F — CPU fallback e latência

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-007-jina-code`

## Objetivo

Provar que o Jina Code 1.5B Q8_0 opera em CPU puro e registrar latência suficiente para decidir viabilidade sem antecipar o benchmark de memória do RAG-007-G

## Execução real

Backend `C:\llama\llama-server.exe`

Modelo `jina-code-embeddings-1.5b-Q8_0.gguf`

Modo CPU explícito

```text
--device none
-ngl 0
```

Health retornou `ok`

PID do teste `11932`

O PID não apareceu em `nvidia-smi --query-compute-apps=pid`

## Embeddings reais em CPU

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

O runtime permaneceu funcional nas duas tarefas já fechadas em RAG-007-D e RAG-007-E

## Interpretação

CPU puro é operacionalmente viável como fallback

A primeira consulta ficou abaixo de 0.34 s e a média warm de NL→code ficou abaixo de 0.06 s neste smoke

O número Code→code é uma única amostra e não deve ser tratado como benchmark estatístico

## Escopo preservado

RAG-007-F não congela RAM VRAM nem prova liberação de memória após unload

Essas medições pertencem ao RAG-007-G

Após o encerramento o PID 11932 foi rechecado e estava ausente

## Estado

RAG-007-F possui prova real de CPU puro e latência registrada
