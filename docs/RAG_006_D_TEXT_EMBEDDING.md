# RAG-006-D — Embedding textual

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-006-jina-text`

## Objetivo

Gerar embeddings locais para o corpus textual definido no handoff

O modelo continua

`Jina v5 Text Small Retrieval`

via

`llama.cpp HTTP local`

## Escopo textual

O handoff define o modelo textual para

- documentação
- handoffs
- roadmaps
- patch notes
- auditorias
- logs resumidos
- mensagens de erro
- metadados Git
- documentação técnica
- português e inglês

No contrato atual isso corresponde a

- DOCUMENTATION
- AUDIT
- LOG
- GIT
- EXECUTION

`CODE` é rejeitado por esta camada

Código-fonte pertence ao Jina Code 1.5B no RAG-007

## Papéis de retrieval

Query

```text
Query: <texto>
```

Documento

```text
Document: <texto>
```

Os prefixos vêm do backend policy congelado no RAG-006-A

## Endpoint

O cliente usa somente

`/v1/embeddings`

do servidor que já precisa estar em

`READY`

RAG-006-D não carrega modelo implicitamente

Não inicia processo

Não baixa modelo

Não marca lifecycle automaticamente

## Contrato do vetor

Dimensão

`1024`

Normalização esperada

`L2 ≈ 1.0`

Tolerância de norma

`1e-3`

Valores não finitos são rejeitados

Resposta com dimensão diferente é rejeitada

## Probe real antes da implementação

Com o GGUF Q4_K_M real e GPU ativa

uma chamada com

- Query repetida duas vezes no mesmo batch
- Document com mesmo texto bruto

retornou

```text
TOP_KEYS=data,model,object,usage
DATA_COUNT=3
DIM=1024
NORMS=1.00000001,1.00000002,0.99999997
REPEAT_MAX_ABS=0.004300474306
QUERY_DOC_COS=0.91559961
ITEM_KEYS=embedding,index,object
```

Isso mostrou que duplicatas dentro do mesmo batch podem apresentar pequena diferença numérica no backend GPU

## Determinismo

Foi feito um segundo probe com cinco chamadas sequenciais independentes para o mesmo

`Query: ownership validation`

Resultado

```text
DIM=1024
NORMS=1.000000004,1.000000004,1.000000004,1.000000004,1.000000004
COSINES=1.000000000,1.000000000,1.000000000,1.000000000
MAX_ABS=0.000000000,0.000000000,0.000000000,0.000000000
```

No ambiente atual chamadas sequenciais foram bit-a-bit iguais

Mesmo assim o contrato público não exige igualdade binária entre hardware/backends

A regra congelada é

`cosine >= 0.9999`

para duas repetições da mesma entrada com o mesmo papel

## Batch inicial

RAG-006-D congela

`TEXT_EMBEDDING_BATCH_SIZE = 1`

`embed_documents` envia um documento por requisição

Motivo

- preservar o comportamento determinístico observado
- evitar depender da variação intra-batch detectada
- deixar throughput e eventual batching para benchmark do RAG-006-G

## Corpus de chunks

`embed_document_chunks`

recebe contratos `Chunk`

e retorna

`DocumentChunkEmbedding`

preservando

- chunk_id
- document_id
- SourceMetadata
- vetor DOCUMENT

Nenhum vetor é persistido nesta fase

## Fronteiras mantidas

RAG-006-D não implementa

- cache por SHA-256
- armazenamento vetorial
- Qdrant
- ranking híbrido
- CPU fallback automático
- benchmark

Cache pertence ao RAG-006-E

CPU fallback ao RAG-006-F

benchmark ao RAG-006-G

índice vetorial ao RAG-009

## Implementação

Criado

`rag/models/embedding.py`

API pública

- TextEmbeddingRole
- TextEmbeddingVector
- DocumentChunkEmbedding
- TextEmbeddingClient
- TextEmbeddingError
- TextEmbeddingStateError
- TextEmbeddingProtocolError
- TextEmbeddingValidationError
- cosine_similarity
- embeddings_are_deterministic

Constantes

- TEXT_EMBEDDING_DIMENSION
- TEXT_EMBEDDING_NORM_TARGET
- TEXT_EMBEDDING_NORM_TOLERANCE
- TEXT_EMBEDDING_DETERMINISM_MIN_COSINE
- TEXT_EMBEDDING_BATCH_SIZE
- TEXT_DOCUMENT_SOURCE_TYPES

Atualizado

`rag/models/__init__.py`

Criado

`tests/test_rag_text_embedding.py`

## Testes unitários

O corpus prova

- dimensão 1024
- batch size 1
- source types textuais
- Query prefix
- Document prefix
- lifecycle precisa estar READY
- dimensão inválida rejeitada
- norma inválida rejeitada
- tolerância de ruído numérico
- protocolo de resposta
- um request por documento
- identidade e metadata do chunk preservadas
- CODE rejeitado
- cosseno e contrato de determinismo
- NaN rejeitado
- ausência de cache e vector store

## Critério de aceitação

RAG-006-D está concluído quando

- Query e Document usam papéis distintos
- dimensão 1024 é validada
- norma unitária é validada
- entradas repetidas passam contrato de determinismo
- corpus textual gera embeddings
- CODE não entra no modelo textual
- nenhuma persistência vetorial foi antecipada
- smoke real passa
- suíte RAG passa
- diff check passa


## Calibração adicional de repetibilidade

Durante o smoke do cliente definitivo, duas chamadas sequenciais iguais retornaram

```text
DETERMINISTIC=False
REPEAT_COS=0.999908298
```

com o limite provisório anterior de `0.999999`

A consulta e o corpus continuaram semanticamente coerentes

```text
SIMS=0.640916312,0.140677045,0.136055435
BEST=doc-load
```

Foi então executada uma calibração com dez chamadas sequenciais no mesmo processo

```text
MIN=0.999908298
MAX=0.999908298
```

O primeiro embedding diferiu ligeiramente das nove chamadas seguintes

Em seguida o servidor foi descarregado e carregado novamente

O primeiro embedding após reload foi comparado com o primeiro embedding salvo da execução anterior

```text
RELOAD_COS=1.000000000
RELOAD_MAX_ABS=0.000000000
```

Isso indica um pequeno efeito numérico de warm-up dentro do processo GPU atual, não deriva entre cargas

Por isso o contrato final foi ajustado para

`TEXT_EMBEDDING_DETERMINISM_MIN_COSINE = 0.9999`

Esse limite aceita a variação observada sem tratar vetores materialmente diferentes como equivalentes

## Smoke real do cliente RAG-006-D

O `TextEmbeddingClient` foi executado contra o modelo real já instalado

Consulta

`como o modelo e carregado sob demanda?`

Corpus

- `doc-load` — carregamento sob demanda e idle
- `doc-fts` — SQLite FTS5 e BM25
- `doc-audit` — auditoria Git e diff

Resultado observado antes do ajuste final da tolerância

```text
DIM=1024
QUERY_NORM=0.999999992
ROLE_COS=0.946384688
CHUNKS=doc-load,doc-fts,doc-audit
DOC_DIMS=1024,1024,1024
DOC_NORMS=0.999999977,1.000000018,0.999999993
SIMS=0.640916312,0.140677045,0.136055435
BEST=doc-load
```

O papel Query e Document produz vetores distintos mesmo com o mesmo texto bruto

O chunk semanticamente relacionado ficou claramente acima dos irrelevantes

Essa comparação é somente sanity check do embedding

Não é ainda ranking vetorial de produção


## Smoke real final após calibração

Com o contrato definitivo de repetibilidade

`TEXT_EMBEDDING_DETERMINISM_MIN_COSINE = 0.9999`

o cliente foi executado novamente contra o GGUF real

Resultado

```text
PID=10820
DIM=1024
QUERY_NORM=0.999999992
REPEAT_COS=0.999908298
DETERMINISTIC=True
ROLE_COS=0.946384688
DOC_NORMS=0.999999977,1.000000018,0.999999993
SIMS=0.640916312,0.140677045,0.136055435
BEST=doc-load
PID_STILL_PRESENT=False
```

O PID é somente o valor da execução de teste

A consulta repetida passou o contrato final

Query e Document permaneceram vetores distintos

Os três embeddings documentais mantiveram dimensão 1024 e norma unitária

O chunk semanticamente relacionado continuou sendo o mais próximo

O unload encerrou o processo real sem PID órfão

## Validação final do RAG-006-D

Testes específicos

```text
Ran 15 tests
OK
```

Suíte RAG completa

```text
Ran 300 tests
OK
```

Git whitespace audit

```text
git diff --check 81517d04fbb7c324d8770aee4c59d38c3fae813d..HEAD
exit_code = 0
```

Worktree de validação estava limpo

```text
## HEAD (no branch)
```

## Estado final

- embedding Query implementado
- embedding Document implementado
- dimensão 1024 validada
- norma unitária validada
- repetibilidade calibrada em GPU real
- batch inicial congelado em 1
- corpus textual permitido congelado
- CODE rejeitado
- metadata de chunk preservada
- smoke real passou
- unload sem processo órfão
- 300 testes RAG passaram
- nenhum cache foi antecipado
- nenhum vector store foi antecipado

RAG-006-D está pronto para fechamento
