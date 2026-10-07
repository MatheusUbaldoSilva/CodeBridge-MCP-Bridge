# RAG-010 — Closeout da busca híbrida

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Estado

`RAG-010 ✅ FECHADO`

O critério do handoff foi cumprido

O CodeBridge agora consegue coletar candidatos FTS5 vetoriais textuais e vetoriais de código executar consulta HYBRID nos dois espaços fundir rankings por Reciprocal Rank Fusion e suprimir chunks praticamente duplicados antes do top-k final

O benchmark de retrieval exigido para fechamento também foi executado e passou

## Base

RAG-010 parte do fechamento do RAG-009

`4dc62b5 docs(rag-009): close vector index milestone`

## RAG-010-A — FTS5 + vetor textual

Commit

`ba745f2 feat(rag-010-a): combine FTS5 and text vector candidates`

Resultado

- FTS5 BM25 preservado
- Qdrant collection text 1024D Cosine
- resultados convertidos para SearchResult
- project namespace obrigatório
- filtros de source type branch e path preservados
- candidatos lexical e vector mantidos separados

Retrieval modes

```text
LEXICAL_FTS5_BM25
VECTOR_TEXT_COSINE
```

## RAG-010-B — FTS5 + vetor de código

Commit

`4e539f3 feat(rag-010-b): combine FTS5 and code vector candidates`

Resultado

- FTS5 BM25 preservado
- Qdrant collection code 1536D Cosine
- project namespace obrigatório
- filtros de source type branch e path preservados
- candidatos lexical e vector mantidos separados

Retrieval mode vetorial

`VECTOR_CODE_COSINE`

## RAG-010-C — Consulta HYBRID

Commit

`5a41115 feat(rag-010-c): search text and code spaces for hybrid queries`

Resultado

Uma consulta com rota

`QueryRoute.HYBRID`

pesquisa

```text
FTS5
+
text vector 1024D
+
code vector 1536D
```

Contrato

`HybridQueryCandidates`

mantém três listas

```text
lexical
text_vector
code_vector
```

Nenhum score heterogêneo é comparado diretamente nesta fase

O classificador determinístico do RAG-008-A pode dirigir a rota HYBRID

Nenhum LLM é usado para escolher a rota

## RAG-010-D — Reciprocal Rank Fusion

Commit

`710eb03 feat(rag-010-d): add deterministic reciprocal rank fusion`

Método

`Reciprocal Rank Fusion`

Constante inicial

`k=60`

Fórmula

```text
RRF(chunk) = soma 1 / (60 + posição)
```

Características

- usa posição e não score bruto
- agrega evidência do mesmo chunk_id em múltiplos rankings
- preserva retrieval modes
- rejeita conflito de conteúdo metadata ou document_id para o mesmo chunk_id
- empate é resolvido deterministicamente
- top_k é aplicado após a fusão

Ordem de desempate

1 maior RRF
2 melhor posição individual
3 chunk_id lexical

## RAG-010-E — Deduplicação

Commit

`0a6ee28 feat(rag-010-e): deduplicate near-identical ranked chunks`

Política

### igualdade normalizada

- Unicode NFKC
- casefold
- tokenização
- diferenças de espaço e pontuação não criam duplicata artificial

### near duplicate longo

Contrato inicial

```text
Jaccard threshold=0.90
min_tokens=12
shingle_size=5
```

Trechos curtos não são colapsados agressivamente

Resultado estruturado

`DeduplicationOutcome`

preserva

- resultados mantidos
- chunks suprimidos
- chunk representante
- similaridade
- motivo da supressão

O top_k é aplicado depois da deduplicação

## Benchmark de retrieval

Commit

`679bcf1 test(rag-010): add hybrid retrieval benchmark`

Pipeline real do benchmark

```text
SQLite FTS5
+
Qdrant Local text
+
Qdrant Local code
↓
HYBRID
↓
RRF
↓
dedup
↓
top 3
```

Casos controlados

```text
cancelamento
handoff memoria
runtime wait
```

Métricas observadas

```text
casos=3
Hit@1=1.000
Recall@3=1.000
MRR=1.000
```

Execução específica observada

```text
Ran 1 test in 0.698s
OK
```

Esse benchmark é de integração determinístico

Não substitui o benchmark amplo com perguntas reais previsto no RAG-014

## Pipeline consolidado

```text
query
↓
classificador determinístico
├── LEXICAL_ONLY
├── TEXT
├── CODE
└── HYBRID
      ↓
      ├── FTS5 BM25
      ├── text vector 1024D
      └── code vector 1536D
              ↓
         RRF k=60
              ↓
      dedup determinístico
              ↓
           top-k
```

## Model Manager preservado

RAG-010 não altera a exclusão mútua dos modelos

Para HYBRID os embeddings de consulta podem ser produzidos sequencialmente

```text
TEXT load
↓
text query embedding
↓
troca segura
↓
CODE load
↓
code query embedding
↓
consulta nos índices persistentes
```

Os dois modelos não precisam permanecer residentes simultaneamente

## Namespace preservado

As buscas vetoriais continuam obrigatoriamente filtradas por projeto

Exemplos

```text
codebridge
new-world-pvp
drones
outros
```

Resultados de projetos diferentes não são misturados

## Fronteiras preservadas

Não pertencem ao RAG-010

### RAG-011

Metadados Git

- HEAD e branch
- commit de proveniência
- arquivos modificados
- staleness relacionado ao estado Git

### RAG-012

Indexação incremental

- arquivo inalterado não reindexa
- arquivo alterado reindexa somente o necessário
- arquivo removido remove chunks órfãos
- mudança de modelo invalida somente o índice correspondente

### RAG-014

Benchmark amplo

- perguntas reais
- corpus real
- métricas de qualidade
- latência e throughput representativos

## Testes

Contagem esperada após adicionar RAG-010-E e o benchmark

`495 testes RAG`

A contagem final é novamente auditada imediatamente antes do commit de closeout

## Critério de fechamento

RAG-010 pode ser marcado fechado porque

- FTS5 + vetor textual existe
- FTS5 + vetor de código existe
- HYBRID pesquisa nos dois espaços
- RRF determinístico foi implementado
- scores heterogêneos não são somados diretamente
- near duplicates são suprimidos de forma auditável
- top_k final preserva diversidade
- benchmark de retrieval passou
- todas as subfases A B C D E possuem commit próprio
- benchmark possui commit próprio
- branch estava sincronizada com origin antes do closeout

## Próximo marco

`RAG-011 — Metadados Git`

Primeiro passo oficial

`RAG-011-A — HEAD/branch`

Objetivo imediato

anexar ao chunk o estado Git necessário para provar de qual branch e HEAD o contexto indexado veio
