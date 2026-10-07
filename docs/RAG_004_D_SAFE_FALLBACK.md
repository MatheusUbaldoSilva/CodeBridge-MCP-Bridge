# RAG-004-D — Fallback seguro

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-004-code-chunking`

## Objetivo

Garantir que uma falha esperada do parser estrutural não faça um arquivo desaparecer silenciosamente do RAG

O handoff exige

- chunking textual controlado
- marcar `parser_mode=fallback`
- nunca perder arquivo silenciosamente

## Fluxo

O fluxo oficial deste subpasso é

```text
arquivo de código
    ↓
parser estrutural
    ↓
sucesso ----------------→ STRUCTURAL
    │                       chunks 004-B
    │                       símbolos 004-C
    │
    └── falha esperada ──→ FALLBACK
                            chunks textuais
                            symbols = ()
                            erro preservado
```

## Parser mode

Criado

`ParserMode.STRUCTURAL`

`ParserMode.FALLBACK`

O modo fica explícito no resultado

Não existe fallback silencioso

## Motivos de fallback

Criado

`FallbackReason.PARSE_ERROR`

para fonte de linguagem registrada cuja estrutura não pôde ser validada

e

`FallbackReason.UNSUPPORTED_LANGUAGE`

para fonte autorizada pelo inventário mas sem parser estrutural registrado nesta etapa

Exemplos atuais

- Bash
- CMD
- BAT

## Chunking textual controlado

Fallback separa primeiro por blocos lógicos delimitados por linhas vazias

Cada bloco é dividido somente quando ultrapassa `fallback_max_lines`

Padrão

`fallback_max_lines = 80`

Partes adicionais do mesmo bloco recebem

`continuation=true`

Não há overlap nesta fase

## Nunca perder arquivo silenciosamente

Todos os trechos não vazios do conteúdo de entrada são preservados em ordem nos chunks de fallback

Linhas vazias usadas apenas como separadores não precisam virar chunks próprios

O teste recompõe todas as linhas não vazias e compara com a entrada original

## Erro original preservado

Em fallback ficam disponíveis

- fallback_reason
- parser_error_type
- parser_error_message

Isso permite diagnóstico sem impedir retrieval textual

## Símbolos

Fallback retorna

`symbols = ()`

Nenhum símbolo é inventado a partir de arquivo que falhou no parser estrutural

A busca ainda poderá encontrar o texto pelos chunks de fallback

## Erros internos inesperados

O fallback captura somente

- `CodeParseError`
- `UnsupportedCodeLanguageError`

Exceções internas inesperadas continuam subindo

Isso evita transformar bug de implementação em fallback aparentemente saudável

## Linguagens estruturais válidas

Quando o parser funciona

`parser_mode=STRUCTURAL`

e o resultado mantém

- chunks estruturais do RAG-004-B
- símbolos do RAG-004-C
- zero chunks de fallback

## Implementação

Criado

`rag/chunking/code_fallback.py`

API pública

- ParserMode
- FallbackReason
- CodeFallbackChunkDraft
- SafeCodeChunkingResult
- safe_chunk_code

Atualizado

`rag/chunking/__init__.py`

## Testes

Criado

`tests/test_rag_code_fallback.py`

Corpus cobre

- Python estrutural válido
- Python inválido
- PowerShell inválido
- C++ inválido
- Bash sem parser
- CMD sem parser
- separação por bloco lógico
- limite controlado
- continuation
- preservação de todas as linhas não vazias
- erro original
- arquivo vazio sem parser
- exceção interna não engolida
- determinismo

## Não antecipado

RAG-004-D não fecha ainda o contrato final de linhas exatas do código

Isso pertence ao RAG-004-E

Também não cria

- SQLite
- FTS5
- embeddings
- Jina

## Critério de aceitação

RAG-004-D está concluído quando

- falha esperada do parser ativa fallback
- parser_mode fica explicitamente FALLBACK
- arquivo suportado e válido continua STRUCTURAL
- conteúdo não vazio não desaparece
- símbolos não são inventados no fallback
- erro original fica disponível
- linguagem sem parser usa fallback textual
- exceção interna inesperada continua visível
- chunking textual possui limite controlado
- testes determinísticos passam
