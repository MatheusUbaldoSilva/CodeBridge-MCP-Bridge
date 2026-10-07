# Fechamento — RAG-004 — Chunking de código

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Status

RAG-004-A ✅

RAG-004-B ✅

RAG-004-C ✅

RAG-004-D ✅

RAG-004-E ✅

Resultado

**RAG-004 FECHADO**

## Objetivo do marco

Implementar chunking de código orientado por estrutura

O marco precisava

- parser por linguagem
- classe função método e bloco lógico como unidade
- símbolos
- fallback textual seguro
- line_start e line_end exatos
- testes com Python PowerShell e C/C++

## RAG-004-A — Parser por linguagem

Commit

`384c15987a6af7c6462dc14f5e37aa28c30ab4ec`

Implementado em

`rag/chunking/code_parser.py`

Cobertura

- Python por AST da biblioteca padrão
- PowerShell por validação lexical própria
- JavaScript por validação lexical ECMAScript
- TypeScript por validação lexical ECMAScript
- C e C++ por validação lexical própria

Linguagens sem parser estrutural não são interpretadas silenciosamente como outra linguagem

## RAG-004-B — Unidades estruturais

Commit

`a48793a98174eab5da3d8bb46c3814c02d400036`

Implementado em

`rag/chunking/code_units.py`

Unidades

- CLASS
- FUNCTION
- METHOD
- LOGICAL_BLOCK

A fronteira primária é estrutural

Não existe corte primário por quantidade de tokens

Classes com métodos evitam duplicação do corpo inteiro

## RAG-004-C — Símbolos

Commit

`16803ba2dc08543c562b5cf9adb562fa946b9535`

Implementado em

`rag/chunking/code_symbols.py`

Símbolos

- MODULE
- CLASS
- FUNCTION
- METHOD
- CONSTANT
- NAMESPACE

Cada símbolo mantém

- name
- qualified_name
- parent
- language
- line_start
- line_end

Python usa AST

PowerShell JavaScript TypeScript e C/C++ usam extração lexical determinística best effort

## RAG-004-D — Fallback seguro

Commit

`6761e2ae44804c66742002669715c1d1c1199200`

Implementado em

`rag/chunking/code_fallback.py`

Modos

- STRUCTURAL
- FALLBACK

Fallback é usado somente em falhas esperadas

- CodeParseError
- UnsupportedCodeLanguageError

Exceções internas inesperadas não são engolidas

Fallback

- preserva conteúdo não vazio
- divide por blocos lógicos
- usa limite controlado
- mantém erro original
- não inventa símbolos
- marca explicitamente parser_mode FALLBACK

## RAG-004-E — Linhas exatas

Commit

`16e3b851d06d60134289179e23ea8b4f81497087`

Implementado em

`rag/chunking/code_lines.py`

Contrato de linha

- coordenadas 1 based
- line_start inclusivo
- line_end inclusivo
- relativas à fonte entregue ao parser

Para chunks estruturais e fallback

```text
chunk.content
==
source_line_slice(source line_start line_end)
```

Ranges fora da fonte são rejeitados

Adulteração de conteúdo ou coordenadas é rejeitada

Símbolos também são validados contra a fonte

## Correção durante auditoria

A primeira montagem do commit RAG-004-E inseriu sequências literais `\n` em `rag/chunking/__init__.py`

A auditoria pré fechamento detectou o problema antes do marco ser concluído

A branch foi regravada a partir do RAG-004-D e o commit final limpo passou a ser

`16e3b851d06d60134289179e23ea8b4f81497087`

O commit defeituoso não permanece na linha oficial da branch

## Validação real no Windows

A suíte foi executada no computador autorizado por CodeBridge usando a rota

```text
codebridge_prepare
→
codebridge_execute_prepared
```

Foi usado worktree temporário em

`%TEMP%\codebridge-rag004-validation`

HEAD validado

`16e3b85 test(rag-004-e): enforce exact code line ranges`

Comando de testes

```text
python -m unittest
tests.test_rag_code_parser
tests.test_rag_code_units
tests.test_rag_code_symbols
tests.test_rag_code_fallback
tests.test_rag_code_lines
-v
```

Resultado real

```text
Ran 64 tests in 0.023s
OK
exit_code = 0
```

A suíte inclui Python PowerShell JavaScript TypeScript C/C++ e fallback

## Git diff check

Executado no mesmo worktree

```text
git diff --check 6761e2ae44804c66742002669715c1d1c1199200..HEAD
```

Resultado

```text
DIFF_CHECK_EXIT=0
```

## Worktree

Após os testes

- worktree temporário removido
- git worktree prune executado
- checkout principal voltou para main
- status principal sem modificações locais

Status observado

```text
## main...origin/main
```

## Commits preservados do RAG-004

```text
384c159  feat(rag-004-a): add language-aware code parsers
a48793a  feat(rag-004-b): chunk code by structural units
16803ba  feat(rag-004-c): extract code symbols
6761e2a  feat(rag-004-d): add safe textual code fallback
16e3b85  test(rag-004-e): enforce exact code line ranges
```

## Invariantes confirmados

1. Python possui parser AST real
2. PowerShell possui parser estrutural próprio
3. C/C++ possui parser estrutural próprio
4. JavaScript e TypeScript possuem parser estrutural lexical
5. classe função método e bloco lógico são unidades disponíveis
6. chunking primário não depende de corte por tokens
7. símbolos são extraídos quando possível
8. falha estrutural esperada usa fallback explícito
9. conteúdo não desaparece silenciosamente em fallback
10. símbolos não são inventados em fallback
11. line_start e line_end são verificáveis contra a fonte
12. adulteração de range ou conteúdo é detectada
13. 64 testes do marco passaram no Windows
14. diff check passou
15. nenhum SQLite foi criado
16. nenhum FTS5 foi criado
17. nenhum embedding foi gerado
18. nenhum modelo Jina foi carregado
19. executor MCP não foi alterado

## Observação sobre a superfície CodeBridge

A tool direta `codebridge_terminal` continuou sendo anunciada pelo catálogo mas rejeitada pelo runtime como Unknown tool

A validação real foi possível pela rota funcional

`codebridge_prepare → codebridge_execute_prepared`

Esse problema de catálogo/runtime é externo ao RAG-004 e não afetou a prova final do marco

## Próximo marco

`RAG-005-A — Schema do índice textual SQLite dedicado ao RAG`

RAG-005 deve começar sem embeddings

FTS5 entra somente após o schema textual do RAG-005-A
