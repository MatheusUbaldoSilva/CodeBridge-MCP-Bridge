# RAG-013 — Integração real MCP

Data 2026-10-07

Projeto CodeBridge 2.0 MCP Bridge

Branch `rag-013-mcp-tools`

## Objetivo

Cumprir o critério final do handoff

`RAG-013 ✅ após integração real MCP`

A validação precisa provar que as tools RAG não funcionam somente como funções Python chamadas diretamente em unit tests

Elas precisam atravessar o transporte MCP real

## Transporte testado

Servidor real

`author_mcp/mcp_server.py`

Transporte

`streamable-http`

Endpoint

`/mcp`

Cliente real

`mcp.ClientSession`

Transporte cliente

`mcp.client.streamable_http.streamable_http_client`

O teste inicia uma instância temporária do MCP em uma porta localhost livre

Depois executa handshake MCP real

`initialize()`

lista as tools com

`list_tools()`

e chama as quatro tools públicas usando

`call_tool()`

## Tools provadas

A lista MCP precisa conter

```text
codebridge_rag_status
codebridge_rag_index
codebridge_search_context
codebridge_get_context
```

Se qualquer uma não estiver registrada o teste falha

## Chamadas reais

### codebridge_rag_status

Executada sem argumentos

A resposta precisa chegar como structured output MCP

E precisa conter

`operation_ok`

### codebridge_rag_index

Executada em modo seguro

```text
project_id=codebridge
project_root=<repo CodeBridge>
scope=BOTH
execute=false
```

Resultado exigido

```text
operation_ok=true
action=PLAN
executed=false
```

Isso também prova que a integração real não dispara indexação pesada silenciosamente

### codebridge_search_context

Executada via transporte MCP com

```text
query=codebridge
project=codebridge
top_k=1
```

A tool precisa responder por structured output

O estado do índice pode produzir sucesso ou erro estruturado conforme o ambiente

O teste prova que não ocorre erro de protocolo MCP

### codebridge_get_context

Executada com um chunk propositalmente inexistente

`integration-missing-chunk`

A resposta ainda precisa atravessar a fronteira MCP como structured output

Isso prova que o contrato público de erro do RAG-013-E permanece estável também no transporte real

## O que é considerado falha

O teste falha se

- servidor MCP não inicia
- handshake falha
- alguma das quatro tools não aparece em list_tools
- call_tool retorna erro de protocolo/tool
- structured output não existe
- rag_index execute=false não retorna PLAN
- rag_index inicia execução apesar de execute=false

## Lifecycle do teste

```text
escolher porta localhost livre
↓
iniciar mcp_server.py real
↓
esperar socket abrir
↓
streamable_http_client
↓
ClientSession
↓
initialize
↓
list_tools
↓
call_tool x4
↓
validar structured outputs
↓
encerrar servidor temporário
```

O processo MCP temporário é terminado no finally

Se não terminar em até 5 segundos é finalizado forçadamente

## Execução observada

Comando

```text
author_mcp\.venv\Scripts\python.exe author_mcp\test_rag_real_mcp_integration.py -v
```

Resultado

```text
test_rag_tools_are_callable_over_real_streamable_http_mcp ... ok

Ran 1 test in 2.596s

OK
```

## Arquivo

Criado

`author_mcp/test_rag_real_mcp_integration.py`

Criado

`docs/RAG_013_MCP_INTEGRATION.md`

## Critério

A superfície proposta no handoff foi registrada no servidor MCP real e chamada através do transporte real

Portanto o requisito de integração real do RAG-013 está satisfeito

O closeout formal ainda exige auditoria Git suíte RAG diff check commit push e auditoria pós commit
