# RAG-009-C — Namespaces de projeto

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-009-vector-index`

## Objetivo

Isolar projetos dentro das coleções vetoriais compartilhadas `text` e `code`

Exemplos do handoff

```text
codebridge
new-world-pvp
drones
outros
```

## Decisão

Namespace de projeto será representado no payload Qdrant pelo campo

`project_namespace`

As coleções continuam separadas apenas por modalidade

```text
text
code
```

Dentro de cada coleção os projetos são isolados por filtro de payload

Isso evita criar uma coleção nova para cada projeto

## Contrato do namespace

Formato canônico

- lowercase ASCII
- letras de a a z
- dígitos
- hífen
- tamanho de 1 a 64
- não começa nem termina com hífen
- não aceita hífens consecutivos
- não aceita espaços
- não faz slug automático

A decisão de não normalizar silenciosamente evita colisões entre IDs diferentes

Exemplo válido

`new-world-pvp`

Exemplo inválido

`New World PvP`

## Payload

Helper

`vector_payload_with_namespace()`

preserva os demais metadados e injeta

```text
project_namespace=<project_id canônico>
```

Se o payload já contiver outro namespace conflitante a operação falha

## Filtro

Helper

`build_project_namespace_filter()`

gera filtro Qdrant equivalente a

```text
project_namespace == namespace solicitado
```

Nenhum storage é aberto ao construir o filtro

## Prova real com Qdrant Local

Foram indexados pontos temporários em dois namespaces dentro da mesma coleção

### text

```text
codebridge
drones
```

Consulta filtrada por `codebridge`

retornou somente o ponto do namespace `codebridge`

### code

```text
new-world-pvp
outros
```

Consulta filtrada por `new-world-pvp`

retornou somente o ponto correspondente

Isso prova isolamento lógico sem criar coleções extras

## Relação com contratos existentes

O CodeBridge já possui `project_id` obrigatório em

- SourceMetadata
- SearchQuery

RAG-009-C não remove nem altera esse contrato

O projeto passa a exigir que o `project_id` usado na camada vetorial esteja no formato canônico de namespace

O payload vetorial usa o campo explícito `project_namespace` para deixar clara a função de isolamento no backend

## IDs dos pontos

Os testes desta fase usam IDs simples apenas para validar filtro de namespace

O contrato de ID de produção ainda não foi congelado

IDs determinísticos pertencem ao RAG-009-D

## Arquivos

Criado

`rag/index/vector_namespace.py`

Atualizado

`rag/index/__init__.py`

Criado

`tests/test_rag_vector_namespace.py`

Criado

`docs/RAG_009_C_NAMESPACES.md`

## Fronteiras

RAG-009-C não define IDs determinísticos

Não implementa reindexação idempotente de chunks

Não implementa busca híbrida

Não altera FTS5

## Critério de aceitação

RAG-009-C está concluído quando

- contrato de namespace é determinístico e estrito
- exemplos do handoff são válidos
- payload sempre recebe namespace
- conflito de namespace é rejeitado
- filtro Qdrant por namespace existe
- isolamento real foi testado em text
- isolamento real foi testado em code
- testes específicos passam
- suíte RAG passa
- git diff check passa
