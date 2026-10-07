# RAG-006-E — Cache de embedding textual

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Evitar recalcular embedding de chunk cujo SHA-256 não mudou

Este cache não é índice vetorial

## SHA do chunk

`SourceMetadata.sha256` representa a fonte de proveniência

O cache precisa invalidar na granularidade do chunk

Por isso o RAG-006-E congela

```text
chunk_sha256 =
SHA256(chunk.content codificado em UTF-8)
```

Mudança em qualquer byte UTF-8 do conteúdo produz miss

Mudança no SHA da fonte sem mudança no conteúdo do chunk não força recomputação

## Namespace do modelo

O hash do chunk sozinho não é suficiente

O mesmo texto precisa ser recalculado se mudar o modelo ou o contrato de embedding

O namespace é SHA-256 determinístico sobre

- versão do contrato de cache
- repository do modelo
- revision imutável
- SHA-256 do GGUF
- quantização
- pooling
- Document prefix
- dimensão

Constante pública

`TEXT_EMBEDDING_CACHE_NAMESPACE`

Uma troca nesses componentes cria um namespace novo e portanto miss natural

## Local do cache

Persistência pertence a

`rag/index/`

conforme o layout RAG congelado

Arquivo padrão

```text
%LOCALAPPDATA%\CodeBridge\cache\rag\
text_embedding_cache.sqlite3
```

Resolução do path não cria diretórios ou banco

A criação só ocorre por conexão explícita

## SQLite dedicado

O cache usa SQLite próprio separado do banco FTS5

Schema version

`1`

Tabela

`rag_text_embedding_cache`

Chave primária

```text
namespace + chunk_sha256
```

Campos

- namespace
- chunk_sha256
- dimension
- vector_blob
- vector_sha256

## Formato do vetor

O vetor é persistido como BLOB de float64 little-endian

Para 1024 dimensões

```text
8192 bytes
```

Isso preserva exatamente os valores float Python retornados pelo cliente

Cada BLOB possui também SHA-256 próprio

Um cache hit só é aceito quando

- namespace bate
- chunk SHA bate
- dimensão bate
- tamanho do BLOB bate
- SHA-256 do BLOB bate
- valores são finitos
- norma ainda passa a validação do TextEmbeddingClient

Corrupção gera erro explícito

Não vira miss silencioso

## Fluxo

```text
Chunk
↓
SHA256(content UTF-8)
↓
lookup namespace + chunk_sha256
├── HIT
│   ↓
│   reconstruir TextEmbeddingVector
│   ↓
│   validar dimensão e norma
│   ↓
│   retornar sem endpoint/modelo
│
└── MISS
    ↓
    TextEmbeddingClient.embed_document
    ↓
    validar vetor
    ↓
    persistir cache
    ↓
    retornar
```

## Modelo pode estar descarregado em hit

Um cache hit não chama

`/v1/embeddings`

Portanto o modelo não precisa estar READY se todos os chunks solicitados já estiverem no cache

Isso será provado em smoke real

Um miss continua exigindo lifecycle READY

## Identidade do resultado

O cache armazena vetor por conteúdo

Ele não armazena chunk_id como identidade do vetor

Ao retornar um hit o resultado usa

- chunk_id atual
- document_id atual
- SourceMetadata atual

Assim chunks diferentes com conteúdo idêntico podem compartilhar vetor sem perder a identidade da consulta atual

## O que não existe

RAG-006-E não implementa

- nearest-neighbor search
- HNSW
- Qdrant
- cosine query no banco
- ranking vetorial
- query embedding cache
- CPU fallback
- benchmark

Índice vetorial pertence ao RAG-009

CPU fallback ao RAG-006-F

benchmark ao RAG-006-G

## Implementação

Criado

`rag/index/embedding_cache.py`

Atualizado

`rag/index/__init__.py`

Atualizado

`rag/models/embedding.py`

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_text_embedding_cache.py`

## Critério de aceitação

RAG-006-E está concluído quando

- chunk SHA é calculado do conteúdo
- conteúdo inalterado gera hit
- conteúdo alterado gera miss
- modelo/namespace alterado gera miss
- hit não chama endpoint
- cache funciona com modelo UNLOADED
- corrupção é detectada
- identidade atual do chunk é preservada
- SQLite é separado do FTS
- nenhum índice vetorial foi antecipado
- smoke real passa
- suíte RAG passa
- diff check passa


## Smoke real com cache e modelo real

Foi criado um SQLite temporário de cache e usado o Jina v5 Text Small real já instalado

Primeira passagem

```text
FIRST_HITS=False,False
CACHE_COUNT=2
```

Os dois chunks foram enviados ao modelo e persistidos no cache

Em seguida o lifecycle foi descarregado

```text
STATE_AFTER_UNLOAD=UNLOADED
```

Os mesmos chunks foram solicitados novamente com o modelo descarregado

Resultado

```text
SECOND_HITS=True,True
COS0=1.000000000
COS1=1.000000000
PID=5720
```

Os vetores retornados do cache foram exatamente equivalentes aos vetores gerados na primeira passagem

Nenhuma requisição de embedding foi necessária para os hits

Uma checagem posterior de processo não encontrou `llama-server.exe` com PID 5720

O código 1 do `findstr` nessa verificação significou ausência de correspondência

Portanto o cache funcionou com o modelo realmente descarregado e sem processo órfão

O banco temporário usado no smoke foi removido ao final do comando

## Ajuste de teste herdado

A primeira suíte completa do RAG-006-E encontrou uma única falha em um teste criado no RAG-006-D

Esse teste exigia que `embedding.py` não contivesse nenhuma referência a cache

Essa regra era correta antes da implementação do RAG-006-E

Ela foi substituída pela fronteira arquitetural correta

`embedding.py` pode coordenar uma interface abstrata de cache mas não pode possuir a persistência

O teste atualizado prova que `embedding.py`

- não importa sqlite3
- não importa rag.index
- não contém Qdrant
- não contém HNSW
- não cria tabela virtual

A persistência concreta permanece exclusivamente em `rag/index/embedding_cache.py`

## Validação final

Testes específicos de embedding + cache

```text
Ran 30 tests
OK
```

Suíte RAG completa

```text
Ran 315 tests
OK
```

Git whitespace audit

```text
git diff --check 6e7c73f1b2914b458bdf92bf9387d453a4931605..HEAD
exit_code = 0
```

Worktree de validação

```text
## HEAD (no branch)
```

sem alterações locais

## Estado final do RAG-006-E

- SHA-256 do conteúdo do chunk congelado
- namespace do modelo congelado
- cache SQLite dedicado implementado
- vetor persistido como float64
- SHA-256 do BLOB validado
- conteúdo inalterado gera hit
- conteúdo alterado gera miss
- mudança de namespace gera miss
- chunks diferentes com mesmo conteúdo compartilham vetor
- SourceMetadata atual é preservado no retorno
- modelo pode estar UNLOADED em cache hit
- corrupção não vira miss silencioso
- nenhum índice vetorial foi antecipado
- smoke real passou
- PID do modelo não permaneceu
- 315 testes RAG passaram
- diff check passou

RAG-006-E está pronto para fechamento
