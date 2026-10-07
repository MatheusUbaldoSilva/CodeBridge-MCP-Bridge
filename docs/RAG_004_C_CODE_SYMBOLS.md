# RAG-004-C — Símbolos de código

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Objetivo

Extrair quando possível os símbolos definidos pelo handoff

- class
- function
- method
- constant
- module
- namespace

A camada de símbolos não altera as fronteiras de chunk definidas no RAG-004-B

## Contrato

Criado `CodeSymbol`

Campos

- ordinal
- name
- qualified_name
- kind
- language
- line_start
- line_end
- parent

Tipos

- CLASS
- FUNCTION
- METHOD
- CONSTANT
- MODULE
- NAMESPACE

## Qualified name

A hierarquia interna usa ponto como separador universal

Exemplos

`src.runtime.Service.run`

`bridge.Network.Client.connect`

Isso facilita retrieval entre linguagens

O conteúdo original da fonte não é reescrito

C++ com `Worker::run` pode ser normalizado semanticamente para `module.Worker.run`

## Module

Todo arquivo com parser registrado recebe um símbolo MODULE

Python usa o path como nome de módulo

Exemplo

`rag/chunking/code_symbols.py`

vira

`rag.chunking.code_symbols`

Para `__init__.py` o nome é o pacote

Outras linguagens usam o stem do arquivo como módulo lógico

## Python

Usa AST real

Extrai

- classes
- funções de módulo
- métodos
- constantes uppercase de módulo
- constantes uppercase diretamente dentro de classe
- módulo

Constantes locais de função não são promovidas para símbolo global

## PowerShell

Extrai quando reconhecível

- class
- method
- function
- filter
- constantes declaradas por `Set-Variable ... -Option Constant`
- módulo

## JavaScript e TypeScript

Extrai

- class
- method
- function
- arrow function atribuída a const let ou var
- binding `const`
- módulo

TypeScript também reconhece

- namespace
- module namespace

Uma arrow function não é duplicada como CONSTANT

## C e C++

Extrai quando reconhecível

- namespace
- class
- struct
- function
- method
- método definido fora da classe com qualificador `::`
- constexpr
- const
- define
- módulo

## Segurança contra falsos símbolos

A extração lexical reutiliza o mascaramento estrutural do RAG-004-B

Strings comentários template strings here-strings e comentários de bloco não criam símbolos falsos

## Best effort

Python tem AST completo nesta fase

PowerShell JavaScript TypeScript e C/C++ ainda usam análise lexical determinística

Por isso o contrato diz quando possível

Nenhuma heurística lexical é tratada como compilador completo

Se o parser base rejeitar a fonte o extrator não inventa símbolos

Fallback pertence ao RAG-004-D

## Linhas

Os símbolos já carregam coordenadas de parser para associação com chunks

A validação final de linhas exatas e invariantes de cobertura continua reservada ao RAG-004-E

## Implementação

Criado

`rag/chunking/code_symbols.py`

API pública

- CodeSymbolKind
- CodeSymbol
- extract_code_symbols

Atualizado

`rag/chunking/__init__.py`

## Testes

Criado

`tests/test_rag_code_symbols.py`

Corpus cobre

- MODULE
- CLASS
- FUNCTION
- METHOD
- CONSTANT
- NAMESPACE
- Python AST
- PowerShell
- JavaScript
- TypeScript
- C/C++
- método C++ fora da classe
- parent
- qualified_name
- strings e comentários
- fonte vazia
- determinismo

## Não antecipado

Esta fase não implementa

- fallback de parser
- chunking textual de arquivo inválido
- parser_mode fallback
- fechamento de line_start line_end
- SQLite
- FTS5
- embeddings
- Jina

## Critério de aceitação

RAG-004-C está concluído quando

- os seis tipos do handoff existem no contrato
- módulo é determinístico pelo path
- Python usa AST
- linguagens lexicais ignoram strings e comentários
- parent e qualified_name preservam hierarquia
- arrow function não duplica como constant
- C++ qualificado pode ser normalizado
- falha do parser não gera símbolos silenciosamente
- testes determinísticos passam
