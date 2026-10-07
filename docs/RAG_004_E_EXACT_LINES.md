# RAG-004-E — Linhas exatas

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Objetivo

Fechar `line_start` e `line_end` como coordenadas exatas de linha lógica para código

O handoff exige manter esses dois campos e o RAG-004 só pode fechar após testes com Python PowerShell e C/C++

## Regra de coordenadas

As linhas são

- 1 based
- inclusivas
- relativas ao conteúdo fonte entregue ao parser
- independentes de byte offset

Exemplo

`line_start=5 line_end=7`

representa exatamente as linhas lógicas 5 6 e 7

## Chunks estruturais

Para todo `CodeUnitDraft`

```text
chunk.content
==
join(source.splitlines()[line_start-1:line_end])
```

Se o conteúdo não corresponder ao slice declarado a validação falha

Isso impede metadata de linha desatualizada ou deslocada

## Chunks fallback

A mesma regra vale para `CodeFallbackChunkDraft`

O fallback não recebe tratamento mais frouxo

Se informar linhas 10 a 12 seu conteúdo deve ser exatamente o conteúdo fonte dessas linhas

## Símbolos

Símbolos não duplicam o texto fonte mas seus ranges precisam

- começar em linha válida
- terminar em linha válida
- permanecer dentro da fonte
- conter o nome do símbolo dentro do range declarado quando não for MODULE

MODULE possui regra própria

```text
line_start = 1
line_end = max(1 total_de_linhas)
```

Isso mantém um módulo explícito mesmo para arquivo vazio

## Teste integrado do marco

O corpus do RAG-004-E passa pelo fluxo real

`safe_chunk_code`

Não usa objetos artificiais para os casos principais

### Python

Congela ranges de

- MODULE
- CONSTANT
- CLASS
- METHOD
- FUNCTION
- chunks estruturais

### PowerShell

Congela ranges de

- MODULE
- CONSTANT
- CLASS
- METHOD
- FUNCTION
- chunks estruturais

### C++

Congela ranges de

- MODULE
- CONSTANT
- NAMESPACE
- CLASS
- METHOD
- FUNCTION
- chunks estruturais

### Fallback

Python estruturalmente inválido é enviado ao fallback e seus chunks também precisam apontar exatamente para o conteúdo original

## Testes negativos

O corpus rejeita

- conteúdo de chunk adulterado
- line_end fora da fonte
- range de símbolo movido para linha que não contém seu nome

## Implementação

Criado

`rag/chunking/code_lines.py`

API pública

- CodeLineAccuracyError
- CodeLineAccuracyReport
- source_line_slice
- validate_code_line_accuracy

Atualizado

`rag/chunking/__init__.py`

## Invariantes do RAG-004 após este subpasso

- parser por linguagem existe
- unidade primária é estrutural
- símbolos são extraídos quando possível
- falha esperada usa fallback explícito
- arquivo não desaparece silenciosamente
- line_start e line_end são verificáveis contra a fonte
- Python PowerShell e C/C++ possuem corpus integrado
- nenhum corte primário por tokens foi introduzido
- nenhum SQLite foi criado
- nenhum FTS5 foi criado
- nenhum embedding foi gerado
- nenhum modelo Jina foi carregado
- executor MCP não foi alterado

## Critério de aceitação

RAG-004-E está concluído quando

- chunks estruturais batem exatamente com seus slices
- chunks fallback batem exatamente com seus slices
- símbolos permanecem dentro da fonte
- MODULE possui range determinístico
- adulteração de conteúdo é detectada
- adulteração de range é detectada
- Python PowerShell e C/C++ passam pelo teste integrado
