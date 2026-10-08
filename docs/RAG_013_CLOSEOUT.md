# RAG-013 — Closeout das Tools MCP

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Estado

`RAG-013 ✅ FECHADO`

O critério do handoff foi cumprido

A superfície RAG pública do CodeBridge agora está registrada no MCP real com contratos estruturados e integração validada através de streamable HTTP

## Base

RAG-013 parte do fechamento do RAG-012

`fdf7d1d docs(rag-012): close incremental indexing milestone`

## RAG-013-A — rag_status

Commit

`25a7d29 feat(rag-013-a): expose read-only RAG status tool`

Tool

`codebridge_rag_status`

Expõe

- índice
- projetos
- modelos
- loaded/unloaded
- backend
- CPU/GPU
- última indexação

Somente leitura

Sem indexação silenciosa

## RAG-013-B — rag_index

Commit

`0413219 feat(rag-013-b): add explicit RAG index MCP tool`

Tool

`codebridge_rag_index`

Contrato

`execute=false`

é o modo seguro padrão

Nesse modo a tool retorna plano e não inicia trabalho pesado

Execução real precisa ser pedida explicitamente

## RAG-013-C — search_context

Commit

`ddadd8f feat(rag-013-c): expose MCP context search`

Tool

`codebridge_search_context`

Entradas públicas

- query
- project
- source_types
- top_k
- path_filter
- branch

O caminho de busca reutiliza os contratos fechados nos marcos anteriores

Quando o executor semântico não está disponível o fallback lexical permanece explícito

## RAG-013-D — get_context

Commit

`efd5789 feat(rag-013-d): expose authorized context retrieval`

Tool

`codebridge_get_context`

Recupera conteúdo autorizado de chunks selecionados

Não aceita path arbitrário como substituto de identidade de chunk

Consulta somente o índice local dentro do projeto autorizado

## RAG-013-E — Contratos de erro

Commit

`11cad1b feat(rag-013-e): stabilize public RAG error contracts`

Falhas públicas são estruturadas

Categorias previstas pelo handoff

- model load
- index unavailable
- source missing
- stale result
- invalid scope

A fronteira MCP não depende de stack trace como contrato público

## Integração MCP real

Commit

`a9d2a70 test(rag-013): prove real MCP tool integration`

Foi criado teste que inicia

`author_mcp/mcp_server.py`

em porta localhost temporária

Transporte real

`streamable-http`

Cliente real

`mcp.ClientSession`

Fluxo validado

```text
server MCP real
↓
initialize
↓
list_tools
↓
call_tool codebridge_rag_status
↓
call_tool codebridge_rag_index
↓
call_tool codebridge_search_context
↓
call_tool codebridge_get_context
```

As quatro tools precisam aparecer em `list_tools`

As quatro chamadas atravessam o transporte MCP real e retornam structured output

O teste também prova que

`codebridge_rag_index execute=false`

retorna

```text
action=PLAN
executed=false
```

sem iniciar indexação pesada

## Execução observada da integração

```text
test_rag_tools_are_callable_over_real_streamable_http_mcp ... ok

Ran 1 test in 2.533s

OK
```

## Suíte RAG final antes do closeout

```text
Ran 611 tests in 15.846s

OK
```

## Auditoria Git

Antes do closeout

```text
git status
clean
```

Integração real já sincronizada

```text
origin/rag-013-mcp-tools...HEAD
0 0
```

## Arquitetura pública consolidada

```text
ChatGPT / cliente MCP
↓
CodeBridge MCP streamable HTTP
├── codebridge_rag_status
├── codebridge_rag_index
├── codebridge_search_context
└── codebridge_get_context
        ↓
     rag_bridge
        ↓
     runtime RAG
        ↓
SQLite FTS5 + Qdrant Local + Model Manager
```

## Fronteiras preservadas

Não pertencem ao RAG-013

### RAG-014

Benchmark próprio com dataset real de 100 consultas

### RAG-015

Segurança de secrets e fontes sensíveis

### RAG-016 e posteriores

Integração de produção e endurecimento adicional conforme roadmap

## Critério de fechamento

RAG-013 pode ser marcado fechado porque

- as quatro tools propostas existem
- rag_status existe
- rag_index exige ação explícita para execução
- search_context existe
- get_context existe
- contratos de erro são estruturados
- integração real MCP foi provada via streamable HTTP
- list_tools expõe as quatro tools
- call_tool funciona nas quatro
- 611 testes RAG passaram
- integração real passou
- branch estava sincronizada antes do closeout

## Próximo marco

`RAG-014 — Benchmark próprio do CodeBridge`

Primeiro passo oficial

`RAG-014-A — Dataset`

Criar 100 consultas reais distribuídas conforme o handoff

- 25 código
- 25 docs/handoffs
- 20 erros/auditorias
- 10 Git
- 10 logs
- 10 PT-BR para código ou termos em inglês
