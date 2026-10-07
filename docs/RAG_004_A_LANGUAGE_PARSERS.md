# RAG-004-A — Parser por linguagem

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Objetivo

Criar a camada inicial de parser por linguagem para código

O handoff manda começar pelas linguagens prioritárias do CodeBridge

Esta fase não define ainda classe função método bloco lógico ou símbolo como unidade final de chunk

Essas decisões continuam reservadas ao RAG-004-B e RAG-004-C

## Linguagens cobertas

### Python

Extensão

`.py`

Backend

`PYTHON_AST`

Usa `ast.parse` da biblioteca padrão Python

Erros de sintaxe preservam linha e coluna quando disponíveis

### PowerShell

Extensão

`.ps1`

Backend

`POWERSHELL_LEXICAL`

Valida estrutura de

- parênteses
- colchetes
- chaves
- strings simples e duplas
- escape por backtick
- comentário de linha
- comentário de bloco
- here-string simples e dupla

Delimitadores dentro de strings comentários e here-strings não contam como estrutura

### JavaScript e TypeScript

Extensões

`.js`

`.ts`

Backend

`ECMASCRIPT_LEXICAL`

Valida delimitadores ignorando comentários strings e template strings

Neste subpasso isso é validação estrutural lexical e não AST ECMAScript completo

### C e C++

Extensões

`.c .cc .cpp .h .hpp`

Backend

`C_CPP_LEXICAL`

Valida delimitadores ignorando comentários e strings

Esse suporte entra já no 004 A porque o próprio marco RAG 004 exige teste final com C/C++

## Linguagens ainda sem parser estrutural

Bash CMD e BAT continuam autorizados pelo inventário do RAG-002-B mas não recebem parser improvisado nesta fase

Quando não existe parser registrado `parse_code_source` retorna erro explícito `UnsupportedCodeLanguageError`

Nenhum arquivo é silenciosamente interpretado como outra linguagem

## Contrato

Criado `rag/chunking/code_parser.py`

API pública

- `CodeLanguage`
- `ParserBackend`
- `CodeParseResult`
- `CodeParseError`
- `UnsupportedCodeLanguageError`
- `detect_code_language`
- `parse_code_source`

`CodeParseResult` contém apenas

- linguagem
- backend
- path
- contagem de linhas
- linhas não vazias
- pares de delimitadores
- profundidade máxima de delimitadores

Ele não contém chunks símbolos funções métodos ou classes

## Separação das próximas fases

RAG-004-A responde

`qual parser usar e a estrutura básica é válida`

RAG-004-B responderá

`qual unidade estrutural deve virar chunk`

RAG-004-C responderá

`quais símbolos pertencem a essa unidade`

RAG-004-D tratará fallback quando parser estrutural falhar

RAG-004-E fechará linhas exatas

## Corpus

Criado `tests/test_rag_code_parser.py`

Coberturas

- detecção por extensão
- Python válido
- Python inválido com linha
- PowerShell com strings comentários e here-string
- PowerShell com delimitador aberto
- JavaScript
- TypeScript
- mismatch ECMAScript
- C/C++
- C/C++ inválido
- Bash CMD BAT explicitamente sem parser
- fonte vazia
- ausência de contrato prematuro de chunks e símbolos
- determinismo
- entrada inválida

## Efeitos colaterais

O parser não

- lê filesystem
- escreve arquivos
- abre SQLite
- cria FTS5
- gera embedding
- carrega Jina
- executa shell
- altera executor MCP

## Critério de aceitação

RAG-004-A está concluído quando

- parser é escolhido deterministicamente pelo path
- Python usa AST real
- PowerShell possui validação estrutural própria
- JavaScript TypeScript possuem validação estrutural própria
- C/C++ possui validação estrutural própria
- strings e comentários não criam falsos delimitadores
- erro estrutural é explícito
- linguagem sem parser não é tratada silenciosamente
- chunk units e símbolos continuam reservados às próximas fases
- testes determinísticos passam
