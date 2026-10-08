# RAG-013-B — Tool MCP codebridge_rag_index

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Expor operação de indexação por MCP de forma explicitamente solicitada

Requisitos do handoff

`Operação explícita de indexação`

`Não iniciar indexação pesada silenciosamente`

## Tool

Nome público

`codebridge_rag_index`

Entradas

```text
project_id
project_root
scope = TEXT | CODE | BOTH
paths = lista opcional
execute = false por padrão
```

## Segurança por padrão

A chamada padrão usa

`execute=false`

Resultado

```text
action=PLAN
executed=false
```

Nenhum modelo é carregado

Nenhum banco é criado

Nenhum embedding é calculado

Nenhuma indexação pesada começa

Isso torna impossível iniciar trabalho pesado apenas por consultar ou descobrir a tool

## Planejamento real

Criado

`rag/runtime/index_request.py`

`plan_rag_index()`

varre o projeto solicitado e aplica as regras já fechadas de inventário

- document source classification
- code source classification
- denylist central

O plano retorna

- quantidade total de candidatos
- candidatos TEXT
- candidatos CODE
- quantidade negada pela denylist
- quantidade fora do escopo
- paths autorizados

## Escopo

TEXT

seleciona somente fontes documentais

CODE

seleciona somente código/config autorizado

BOTH

seleciona os dois conjuntos sem misturar arquivos negados

## Paths explícitos

A tool pode receber uma lista de arquivos ou diretórios

Quando fornecida somente esse subconjunto é planejado

Path fora do project_root é rejeitado

Path inexistente é rejeitado

## Execução explícita

Para trabalho pesado são necessárias duas condições simultâneas

```text
execute=true
+
executor RAG registrado
```

Sem executor registrado a resposta é erro estruturado

`RagIndexExecutionUnavailableError`

Isso é deliberado

A superfície MCP não inventa uma indexação e não marca arquivos como indexados sem um executor real

## Executor

O bridge possui registro explícito

`register_rag_index_executor()`

O executor recebe um `RagIndexPlan` já validado

A tool só chama esse executor quando `execute=true`

Nos testes foi provado que

- execute=false não chama executor
- execute=true chama exatamente uma vez
- execute=true sem executor não finge sucesso

## Isolamento do MCP

`author_mcp/mcp_server.py` continua sem importar o pacote RAG no import crítico

A tool usa

`author_mcp/rag_bridge.py`

e o pacote RAG é importado somente na chamada

Falha do RAG retorna contrato estruturado e não derruba as demais tools

## Integração MCP real

A suíte usa o Python real de

`author_mcp/.venv`

e valida que

`codebridge_rag_index`

está registrado no MCPServer real

Também valida o caminho PLAN e o caminho EXECUTE com executor registrado

## Estado de integração

A tool MCP e o contrato explícito de execução estão fechados nesta subfase

O processo principal ainda precisa registrar o executor pesado real antes do fechamento completo do RAG-013

Portanto

```text
RAG-013-B tool/API ✅
executor pesado de produção → requisito de integração final do RAG-013
```

Isso mantém a fase honesta e evita declarar indexação inexistente

## Capabilities

`codebridge_rag_index`

foi adicionado à lista de tools preferenciais de `codebridge_capabilities`

## Arquivos

Criado

`rag/runtime/index_request.py`

Atualizado

`rag/runtime/__init__.py`

Atualizado

`author_mcp/rag_bridge.py`

Atualizado

`author_mcp/mcp_server.py`

Criado

`tests/test_rag_index_request.py`

Criado

`tests/test_rag_mcp_index_tool.py`

Criado

`docs/RAG_013_B_RAG_INDEX.md`

## Testes específicos

```text
Ran 12 tests
OK
```

Validações incluem

- planejamento BOTH
- planejamento TEXT
- planejamento CODE
- paths explícitos
- denylist
- namespace
- path traversal
- padrão PLAN-only
- executor obrigatório
- executor chamado uma vez
- tool registrada no MCP real
- erro estruturado sem executor
- execução explícita via executor registrado

## Fronteiras

RAG-013-B não implementa busca MCP

Isso pertence ao RAG-013-C

RAG-013-B não recupera conteúdo completo

Isso pertence ao RAG-013-D

Contratos de erro comuns serão consolidados no RAG-013-E

O executor pesado real deve ser registrado antes do closeout do RAG-013
