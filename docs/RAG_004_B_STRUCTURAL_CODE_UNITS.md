# RAG-004-B — Unidade estrutural de código

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Objetivo

Evitar corte cego por quantidade de tokens

Preferir as unidades estruturais definidas pelo handoff

- classe
- função
- método
- bloco lógico

## Contrato

Criado `CodeUnitDraft`

Campos

- ordinal
- content
- language
- kind
- line_start
- line_end

Tipos de unidade

- CLASS
- FUNCTION
- METHOD
- LOGICAL_BLOCK

O contrato não contém nome de símbolo

A extração de nomes continua reservada ao RAG-004-C

## Estratégia sem overlap estrutural excessivo

Funções e métodos recebem o corpo completo

Classe sem métodos pode permanecer inteira como uma unidade CLASS

Classe com métodos não duplica o corpo inteiro

Nesse caso

1 o cabeçalho estrutural da classe vira CLASS
2 cada método vira METHOD
3 atributos constantes imports comentários ou outros trechos restantes viram LOGICAL_BLOCK
4 chaves isoladas de fechamento não viram chunks inúteis

Essa estratégia reduz duplicação de contexto sem cortar por tokens

## Python

Usa AST real

Funções de módulo viram FUNCTION

Métodos diretamente pertencentes a classes viram METHOD

Classes sem filhos estruturais podem permanecer inteiras

Classes com métodos ou classes internas usam cabeçalho estrutural separado

Decorators permanecem associados à unidade correspondente

## PowerShell

Detecta

- class
- function
- filter
- métodos dentro de class

Strings comentários block comments e here-strings são mascarados para não criarem falsos delimitadores

## JavaScript e TypeScript

Detecta

- class
- function
- métodos de class
- arrow functions atribuídas a const let ou var

Strings comentários e template strings são mascarados

Arrow function de expressão pode ser uma unidade de uma única linha

## C e C++

Detecta

- class
- struct
- funções
- métodos dentro de class ou struct

Controles como if for while switch catch e return não são tratados como função

## Bloco lógico

Código significativo que não pertence a uma unidade estrutural vira LOGICAL_BLOCK

Exemplos

- imports
- constantes
- atributos de classe
- campos
- declarações auxiliares

Linhas contendo somente pontuação estrutural como uma chave isolada não criam chunk próprio

## Sem corte por tokens

`chunk_code_units` não recebe

- max_tokens
- token_limit
- tokens

O tamanho futuro poderá ser controlado por fallback específico quando realmente necessário

A fronteira primária continua sendo estrutura do código

## Separação do RAG-004-C

RAG-004-B sabe que uma unidade é METHOD ou FUNCTION

Ele ainda não publica o nome do método ou função

O próximo subpasso extrairá quando possível

- class
- function
- method
- constant
- module
- namespace

## Implementação

Criado

`rag/chunking/code_units.py`

API pública

- CodeUnitKind
- CodeUnitDraft
- chunk_code_units

Atualizado

`rag/chunking/__init__.py`

## Testes

Criado

`tests/test_rag_code_units.py`

Corpus cobre

- Python
- PowerShell
- JavaScript
- TypeScript
- C++
- class
- function
- method
- logical block
- classe sem métodos
- arrow function
- unidades não sobrepostas
- ausência de token slicing
- ausência de nome de símbolo no contrato
- propagação de erro estrutural
- linguagem sem parser
- fonte vazia
- determinismo

## Efeitos colaterais

Esta camada não

- abre SQLite
- cria FTS5
- gera embeddings
- carrega Jina
- executa shell
- altera executor MCP

## Critério de aceitação

RAG-004-B está concluído quando

- classe função método e bloco lógico existem como unidades
- fronteiras estruturais vencem tamanho arbitrário
- classes com métodos não duplicam o corpo inteiro por padrão
- unidades primárias não se sobrepõem
- nomes de símbolos continuam fora deste contrato
- linguagens sem parser não entram silenciosamente
- testes determinísticos passam
