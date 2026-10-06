# RAG-003-A — Chunking de Markdown

Data: 2026-10-06
Projeto: CodeBridge 2.0 — MCP Bridge
Branch: `rag-003-text-chunking`

## Objetivo

Implementar o primeiro chunker textual do RAG

O handoff exige separar Markdown preferencialmente por

- heading
- subsection
- bloco lógico

A implementação segue exatamente essa ordem de prioridade

## Estratégia

### Heading

Um novo heading inicia uma nova seção

São reconhecidos headings ATX de H1 até H6 e headings Setext

### Subsection

O chunker mantém uma pilha de headings

Exemplo conceitual

- Alpha
- Alpha > Beta
- Alpha > Beta > Gamma

Ao voltar para um nível superior a pilha é reduzida deterministicamente

### Bloco lógico

Dentro de uma seção Markdown blocos separados por linhas vazias viram unidades independentes

Isso preserva naturalmente parágrafos listas contíguas blockquotes contíguos e blocos de código cercados

O primeiro bloco de uma seção mantém o heading junto ao conteúdo

Blocos seguintes mantêm `heading_path` como contexto estrutural

## Blocos de código cercados

Fences com crase ou til são reconhecidos

Um `#` dentro de fence não cria seção

Linhas vazias dentro do fence também não dividem o bloco

## Contrato produzido neste subpasso

Criado `MarkdownChunkDraft`

Campos

- ordinal
- content
- heading_path
- heading_level
- line_start
- line_end
- kind

Tipos de chunk

- PREAMBLE
- SECTION

Os campos de linha são coordenadas determinísticas do parser e ajudam os testes

O contrato completo de proveniência com path SHA-256 data source_type e project_id continua reservado ao RAG-003-D

## Preamble

Texto antes do primeiro heading não é descartado

Ele é dividido em blocos lógicos e marcado como PREAMBLE

## Documento sem headings

Markdown sem heading usa diretamente blocos lógicos

## Overlap

RAG-003-A aplica overlap zero

Overlap controlado pertence ao RAG-003-C e não foi antecipado

## IDs e integração com Chunk

Este subpasso produz drafts determinísticos

A transformação final para o contrato `Chunk` com proveniência completa será feita quando o RAG-003-D congelar os metadados obrigatórios

Isso evita inventar SHA path data ou project_id antes da fase correta

## Implementação

Criado `rag/chunking/markdown.py`

API pública

- MarkdownChunkKind
- MarkdownChunkDraft
- chunk_markdown

Também criado `rag/chunking/__init__.py`

## Corpus de teste

Criado em `tests/test_rag_markdown_chunking.py`

O corpus cobre preamble H1 H2 Setext H1 subseção múltiplos blocos lógicos lista fenced code linha vazia dentro de fenced code `#` falso dentro de código título contendo C# heading sem corpo documento sem headings linhas determinísticas ausência de overlap e determinismo entre execuções

## Efeitos colaterais

O chunker não lê filesystem não escreve arquivo não abre SQLite não cria FTS5 não gera embedding não carrega Jina não executa shell e não altera executor MCP

## Critério de aceitação do RAG-003-A

RAG-003-A está concluído quando headings criam fronteiras determinísticas subseções mantêm hierarquia bloco lógico funciona como fallback fences impedem headings falsos preamble não é perdido documento sem heading continua chunkável nenhum overlap é aplicado testes determinísticos passam e nenhuma fase posterior foi antecipada
