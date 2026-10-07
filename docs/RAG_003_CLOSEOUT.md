# Fechamento — RAG-003 — Chunking de texto

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-003-text-chunking`

## Status

RAG-003-A ✅

RAG-003-B ✅

RAG-003-C ✅

RAG-003-D ✅

Resultado **RAG-003 FECHADO**

## RAG-003-A Markdown

Implementado `rag/chunking/markdown.py`

Estratégia congelada

- heading
- subsection
- bloco lógico

Suporta headings ATX H1 até H6 headings Setext preamble documento sem heading e fenced code sem falso heading

Overlap permaneceu zero nesta fase

Corpus versionado em `tests/test_rag_markdown_chunking.py`

Validação isolada registrada durante a fase 12 de 12 casos

Commit preservado

`35d68ca716a840e85563141abfdebaafac4edd3a`

## RAG-003-B TXT e logs

Implementado `rag/chunking/text_log.py`

Fronteiras congeladas

- SECTION
- EXECUTION
- ERROR
- EVENT
- BLOCK

Limite padrão `max_lines=80`

Continuação forçada recebe `continuation=true`

Nenhuma linha é duplicada pelo chunker base

Corpus versionado em `tests/test_rag_text_log_chunking.py`

Validação isolada registrada durante a fase 12 de 12 casos

Commit preservado

`b5b5b80b2ca59c82253876c778a5f8f8213a6ce3`

## RAG-003-C overlap controlado

Implementado `rag/chunking/overlap.py`

Overlap padrão somente para continuação forçada

Parâmetros padrão

- overlap_lines 2
- max_overlap_lines 4
- max_overlap_fraction 0.25

Nova fronteira semântica não recebe overlap

Markdown não recebe overlap por padrão

Chunks originais permanecem imutáveis

Corpus versionado em `tests/test_rag_controlled_overlap.py`

Validação isolada registrada durante a fase 12 de 12 casos

Commit preservado

`8aec852d0f6f89d1f46b972ea8a6aaed494289d9`

## RAG-003-D proveniência

Implementado `rag/chunking/provenance.py`

Cada Chunk criado mantém obrigatoriamente

- project_id
- path
- line_start
- line_end
- sha256
- indexed_at
- source_type

O SHA-256 é calculado sobre o documento fonte inteiro em UTF-8

O conteúdo do draft é relido pela faixa de linhas e deve coincidir exatamente com a fonte recebida

Paths absolutos path traversal Windows drive e UNC são rejeitados

`indexed_at` exige ISO-8601 com timezone

IDs são fornecidos pelo chamador para não antecipar RAG-009-D

Corpus versionado em `tests/test_rag_chunk_provenance.py`

A lógica central de proveniência foi executada isoladamente e passou validação de hash path linhas timezone e criação dos Chunk contracts

Commit preservado

`fbd419c44d4da50d26e1ae5ad40f3ce93a74da2d`

## Auditoria do commit RAG-003-D

Comparação direta contra RAG-003-C confirmou

- ahead_by 1
- behind_by 0
- total_commits 1

Somente quatro arquivos pertencem ao diff

- `docs/RAG_003_D_CHUNK_PROVENANCE.md`
- `rag/chunking/__init__.py`
- `rag/chunking/provenance.py`
- `tests/test_rag_chunk_provenance.py`

Nenhum placeholder temporário permaneceu no histórico oficial após a regravação da branch

## Limitação de validação local

O CodeBridge respondeu handshake READY nas tentativas desta frente porém as tools de execução retornaram `Unknown tool` no runtime

Também não foi possível baixar a branch pública pelo ambiente isolado para executar um checkout completo

Por isso este fechamento não afirma uma execução completa da suíte no Windows

A evidência usada foi

- testes determinísticos versionados
- validações isoladas dos subpassos
- validação isolada da proveniência
- revisão de diff pós commit
- auditoria de branch e commits

Quando a superfície MCP de execução voltar consistente a suíte versionada pode ser executada sem alterar o desenho do RAG-003

## Invariantes confirmados

1 chunking Markdown é determinístico

2 chunking TXT e log é determinístico

3 overlap não é global

4 overlap não modifica chunk fonte

5 proveniência é validada contra conteúdo fonte

6 SHA-256 representa o snapshot da fonte inteira

7 linhas permanecem exatas

8 source_type usa contrato oficial

9 project_id é obrigatório

10 IDs determinísticos não foram antecipados

11 nenhum SQLite foi criado

12 nenhum FTS5 foi criado

13 nenhum embedding foi gerado

14 nenhum modelo Jina foi carregado

15 executor MCP não foi alterado

## Próximo marco

`RAG-004-A — Parser por linguagem`

O próximo marco começa chunking estrutural de código

Começar pelas linguagens prioritárias do CodeBridge sem corte cego por tokens e sem antecipar SQLite embeddings ou modelos
