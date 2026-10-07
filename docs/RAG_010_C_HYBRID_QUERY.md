# RAG-010-C — Consulta HYBRID

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-010-hybrid-search`

## Objetivo

Quando o classificador determinístico selecionar `HYBRID` pesquisar simultaneamente

- FTS5 lexical
- espaço vetorial textual
- espaço vetorial de código

sem antecipar a fusão de ranking do RAG-010-D nem a deduplicação do RAG-010-E

## Entrada

`collect_hybrid_query_candidates()`

recebe

- conexão SQLite do índice lexical
- cliente Qdrant Local
- `SearchQuery`
- rota `QueryRoute.HYBRID`
- query vector textual 1024D
- query vector de código 1536D

A rota precisa ser explicitamente `HYBRID`

Chamadas com TEXT CODE ou LEXICAL_ONLY são rejeitadas nesta API

## Relação com o classificador

RAG-008-A já definiu regras determinísticas

Exemplo de consulta

`onde o código implementa o que está no handoff`

classifica como

`HYBRID`

RAG-010-C usa essa decisão para consultar os dois espaços vetoriais

Nenhum LLM é usado para escolher a rota

## Fluxo

```text
SearchQuery
    ↓
QueryRoute.HYBRID
    ├── FTS5 BM25
    │      ↓
    │   lexical
    │
    ├── text query embedding 1024D
    │      ↓
    │   Qdrant collection text
    │      ↓
    │   text_vector
    │
    └── code query embedding 1536D
           ↓
        Qdrant collection code
           ↓
        code_vector

lexical + text_vector + code_vector
                ↓
      HybridQueryCandidates
```

## Resultado

`HybridQueryCandidates`

contém três listas independentes

```text
lexical
text_vector
code_vector
```

Cada item continua usando o contrato comum

`SearchResult`

Os retrieval modes permanecem próprios de cada mecanismo

- `LEXICAL_FTS5_BM25`
- `VECTOR_TEXT_COSINE`
- `VECTOR_CODE_COSINE`

## Por que não fundir agora

Os scores têm naturezas diferentes

FTS5 usa BM25 convertido para higher is better

Qdrant usa similaridade Cosine

Somar ou comparar os valores crus nesta fase criaria uma política acidental

Por isso RAG-010-C apenas coleta os três conjuntos

A fusão determinística fica isolada no RAG-010-D

## Model Manager

RAG-010-C trabalha com embeddings já produzidos

A geração dos vetores text e code deve respeitar a exclusão mútua fechada no RAG-008

Isso permite o fluxo

```text
classificar HYBRID
↓
carregar TEXT
↓
gerar query vector textual
↓
descarregar ou trocar conforme Model Manager
↓
carregar CODE
↓
gerar query vector de código
↓
consultar ambos os índices persistentes
```

RAG-010-C não altera a política de residência dos modelos

## Filtros

Cada espaço reutiliza as regras já fechadas em RAG-010-A e RAG-010-B

- project namespace
- source_types
- branch
- path_filter

O mesmo `SearchQuery` é usado nas três pesquisas

## Prova real

Foi criado corpus temporário com

- um chunk encontrado lexicalmente
- um chunk textual semanticamente mais próximo
- um chunk de código semanticamente mais próximo

Consulta

`handoff explica cancelamento`

Resultado

```text
lexical[0]     = chunk-lexical
text_vector[0] = chunk-text
code_vector[0] = chunk-code
```

Isso prova que uma única consulta HYBRID alcança os três espaços

## Isolamento de projeto

Foram indexados vetores text e code para

`codebridge`

e

`drones`

Consulta HYBRID em

`codebridge`

retornou somente os vetores do namespace codebridge em ambos os espaços

## Validação de dimensão

A dimensão é validada pelo caminho específico

`text_query_vector` exige 1024D

`code_query_vector` exige 1536D

Dimensão incorreta é rejeitada antes da consulta correspondente

## Arquivos

Criado

`rag/retrieval/hybrid_query.py`

Atualizado

`rag/retrieval/__init__.py`

Criado

`tests/test_rag_hybrid_query.py`

Criado

`docs/RAG_010_C_HYBRID_QUERY.md`

## Fronteiras

RAG-010-C não implementa

- Reciprocal Rank Fusion
- normalização conjunta de scores
- escolha de peso entre fontes
- deduplicação
- benchmark final de retrieval

Esses itens pertencem aos próximos passos

RAG-010-D fusão

RAG-010-E deduplicação

closeout do RAG-010 com benchmark de retrieval

## Critério de aceitação

RAG-010-C está concluído quando

- classificador pode produzir HYBRID
- API exige rota HYBRID
- FTS5 é consultado
- vetor textual é consultado
- vetor de código é consultado
- três rankings permanecem separados
- namespace vale nos dois espaços vetoriais
- dimensões text e code são validadas
- testes específicos passam
- suíte RAG passa
- git diff check passa
