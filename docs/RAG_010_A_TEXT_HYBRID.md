# RAG-010-A — FTS5 + vetor textual

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Combinar a recuperação lexical FTS5 já existente com recuperação vetorial textual persistida no Qdrant Local

Requisito do handoff

`FTS5 + vetor textual — Combinar resultados`

RAG-010-D ainda é responsável pela fusão final de ranking

RAG-010-E ainda é responsável por deduplicação

Por isso RAG-010-A reúne os dois conjuntos de candidatos mas mantém suas ordens e scores separados

## Recuperação lexical

Continua usando o contrato já fechado

`search_lexical_ranked()`

Modo

`LEXICAL_FTS5_BM25`

O ranking lexical continua BM25 com maior score público sendo melhor

Nenhuma política lexical foi alterada nesta fase

## Recuperação vetorial textual

Criado

`search_text_vector()`

Entrada

- Qdrant Local client
- SearchQuery
- query vector textual de 1024 dimensões

Coleção

`text`

Distância

`Cosine`

Modo de retrieval

`VECTOR_TEXT_COSINE`

O score retornado pelo Qdrant é preservado como score vetorial

## Namespace

Toda consulta vetorial textual aplica obrigatoriamente

`project_namespace == query.project_id`

Assim resultados de outro projeto não entram no conjunto vetorial

## Filtros

Source types

quando fornecidos são aplicados no filtro Qdrant

Branch

quando fornecida é aplicada como match exato

Path filter

mantém a semântica de substring já usada pelo caminho lexical

Para preservar essa semântica o candidato vetorial é pós filtrado por path

Quando existe path_filter a fase consulta todos os pontos elegíveis do namespace e filtros exatos antes de aplicar a substring

Essa escolha prioriza correção nesta fase

Benchmark e otimização ficam para os marcos de avaliação

## Payload necessário

O ponto vetorial textual precisa conter pelo menos

- chunk_id
- document_id
- content
- source_type
- project_namespace

Metadados opcionais reaproveitados

- path
- symbol
- line_start
- line_end
- git_branch
- git_commit
- sha256
- indexed_at
- source_id

O resultado é convertido para o contrato comum

`SearchResult`

## Candidatos híbridos textuais

Criado

`TextHybridCandidates`

contendo

```text
lexical: tuple[SearchResult]
vector: tuple[SearchResult]
```

Criado

`collect_text_hybrid_candidates()`

Fluxo

```text
SearchQuery
   ├── FTS5 BM25
   │      ↓
   │   lexical candidates
   │
   └── text query embedding
          ↓
       Qdrant text
          ↓
       vector candidates

lexical + vector
       ↓
TextHybridCandidates
```

Nesta fase os resultados ainda não são fundidos em um único ranking

Isso evita antecipar RAG-010-D

## Prova real

Corpus de teste persistiu dois chunks no SQLite/FTS5 e no Qdrant Local

Consulta

`cancelamento`

O FTS5 encontrou

`chunk-lexical`

O vetor textual colocou

`chunk-vector`

na primeira posição semântica

O bundle final preservou simultaneamente

- candidatos lexicais
- candidatos vetoriais

com seus retrieval_modes independentes

## Isolamento provado

Foram indexados vetores nos namespaces

`codebridge`

e

`drones`

Consulta no projeto codebridge retornou somente o ponto codebridge

## Path filter provado

Foram indexados

`docs/guide.md`

e

`src/internal.txt`

Filtro

`docs/`

retornou somente o chunk do caminho docs

## Arquivos

Criado

`rag/retrieval/hybrid_text.py`

Atualizado

`rag/retrieval/__init__.py`

Criado

`tests/test_rag_hybrid_text.py`

Criado

`docs/RAG_010_A_TEXT_HYBRID.md`

## Fronteiras

RAG-010-A não implementa

- vetor de código combinado com FTS5
- consulta HYBRID entre espaços text e code
- Reciprocal Rank Fusion
- deduplicação de chunks

Esses pontos pertencem respectivamente a RAG-010-B C D E

## Critério de aceitação

RAG-010-A está concluído quando

- FTS5 continua retornando SearchResult
- Qdrant text retorna SearchResult
- namespace é obrigatório no vetor
- source type e branch podem filtrar vetor
- path filter preserva substring
- bundle contém lexical e vector
- nenhum algoritmo de fusão foi antecipado
- testes específicos passam
- suíte RAG passa
- git diff check passa
