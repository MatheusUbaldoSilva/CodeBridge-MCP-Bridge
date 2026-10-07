# RAG-009-B — Coleções vetoriais separadas text e code

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-009-vector-index`

## Objetivo

Criar no backend congelado em RAG-009-A duas coleções vetoriais fisicamente separadas

```text
text
code
```

sem antecipar namespaces de projeto nem IDs determinísticos

## Dependência controlada

Instalado no ambiente de desenvolvimento

`qdrant-client==1.19.1`

A versão também foi adicionada ao `requirements.txt`

O adapter continua com import lazy

Importar `rag.index.qdrant_local` não importa `qdrant_client` e não abre armazenamento

## Backend

Qdrant Local persistido em disco

Nenhum servidor externo é iniciado

Nenhum Docker é necessário no caminho inicial

Path padrão

`%LOCALAPPDATA%\CodeBridge\rag\qdrant`

O path pode ser explicitamente substituído em testes e integrações

## Contrato das coleções

### text

```text
name=text
dimension=1024
distance=Cosine
```

A dimensão vem do contrato já congelado do modelo textual

`TEXT_EMBEDDING_DIMENSION`

### code

```text
name=code
dimension=1536
distance=Cosine
```

A dimensão vem do contrato já congelado do Jina Code

`CODE_EMBEDDING_DIMENSION`

## Criação idempotente

`ensure_vector_collections()`

para cada coleção

```text
collection existe?
├── não → criar com contrato esperado
└── sim → não recriar
          ↓
       verificar contrato
```

Executar ensure mais de uma vez não cria coleções duplicadas

## Validação de contrato

Se uma coleção existente tiver dimensão diferente do esperado a operação falha explicitamente com

`QdrantCollectionContractError`

A mesma validação existe para distância vetorial

Nesta fase cada coleção usa um único vetor denso sem nome

## Smoke real

Foi criado Qdrant Local em diretório temporário

Resultado

```text
['text', 'code']
TEXT 1024 Cosine
CODE 1536 Cosine
PERSISTED True
```

O storage foi fechado e reaberto

As duas coleções continuaram existentes

Chamadas repetidas de `ensure_vector_collections()` mantiveram apenas

```text
code
text
```

sem duplicação

## Compatibilidade Python 3.13

Durante a validação apareceu um `ResourceWarning` vindo do probe interno de SQLite do qdrant-client 1.19.1

A origem foi auditada

`CollectionPersistence.__init__`

usa uma conexão SQLite temporária para descobrir a opção THREADSAFE

No Python 3.13 o context manager de sqlite3 não fecha a conexão ao sair e a coleta posterior emite aviso de conexão não fechada

O adapter passou a executar o mesmo probe antes do Qdrant mas com `connection.close()` explícito

Depois da correção a suíte específica foi executada com

```text
python -W error::ResourceWarning -m unittest tests.test_rag_qdrant_local_collections -v
```

Resultado

```text
Ran 7 tests
OK
```

sem ResourceWarning

Nenhum arquivo do pacote qdrant-client instalado foi modificado

A compatibilidade fica isolada no adapter do CodeBridge

## Lifecycle do storage

`open_qdrant_local()`

abre o cliente persistente

`close_qdrant_local()`

exige e chama `close()` explicitamente

Os testes usam fechamento explícito antes de destruir diretórios temporários

## Arquivos

Criado

`rag/index/qdrant_local.py`

Atualizado

`rag/index/__init__.py`

Atualizado

`requirements.txt`

Criado

`tests/test_rag_qdrant_local_collections.py`

Criado

`docs/RAG_009_B_COLLECTIONS.md`

## Fronteiras

RAG-009-B não implementa

- namespace de projeto
- payload final de proveniência
- IDs determinísticos
- upsert de chunks de produção
- busca nearest neighbor de produção
- fusão com FTS5

Namespaces pertencem ao RAG-009-C

IDs e reindexação idempotente pertencem ao RAG-009-D

Busca híbrida pertence ao RAG-010

## Critério de aceitação

RAG-009-B está concluído quando

- qdrant-client 1.19.1 está pinado
- storage local persistente abre e fecha
- coleção text existe com 1024D cosine
- coleção code existe com 1536D cosine
- coleções permanecem separadas
- reopen preserva coleções
- ensure é idempotente
- contrato incompatível é rejeitado
- import do adapter permanece lazy
- não existe ResourceWarning conhecido no ciclo testado
- testes específicos passam
- suíte RAG passa
- git diff check passa
