# CodeBridge — Catálogo de ferramentas MCP

Referência dos nomes declarados no servidor `author_mcp/mcp_server.py` e dos contratos expostos na conexão em uso. **Declarada no código** não significa necessariamente **publicada na conexão atual**.

## Estado e descoberta

| Nome | Chamada / argumentos | O que retorna |
|---|---|---|
| `codebridge_status` | `{}` | Handshake, status READY, app, versão, filas, executor, disponibilidade dos terminais |
| `codebridge_capabilities` | `{}` | Alvos aceitos, recursos, limites e ferramentas preferidas |
| `codebridge_read_batch` | `{requests:[...]}` (conferir schema do servidor) | Lote validado de operações estritamente somente leitura |

## Execução e terminal

| Nome | Parâmetros importantes | Efeito |
|---|---|---|
| `codebridge_prepare` | `target, command` | Prepara comando, sem Enter |
| `codebridge_execute_prepared` | `prepared_request_id` | Envia Enter do comando preparado uma vez |
| `codebridge_discard` | `request_id` opcional | Descarta comando preparado |
| `codebridge_exec` | `target, command, wait_timeout_ms, output_mode` | Inicia/acompanha execução no terminal |
| `codebridge_wait` | `execution_id, cursor, wait_timeout_ms, max_chars, output_mode` | Lê saída e estado do ID sem novo Enter |
| `codebridge_stop` | `execution_id` opcional | Interrompe execução indicada ou fluxo ativo/preparado |

```json
{"target":"CMD","command":"ver","wait_timeout_ms":1500,"output_mode":"NORMAL"}
```

Exemplo para `codebridge_exec`. Em caso de retorno `RUNNING`, continuar por `codebridge_wait`, não repetir a chamada acima.

## Conhecimento/RAG

| Nome | Parâmetros importantes | Comportamento |
|---|---|---|
| `codebridge_rag_status` | `{}` | Geração, índice, backend, modelos e projetos |
| `codebridge_rag_index` | `project_id, project_root, scope, paths, execute` | Prévia da elegibilidade; execução condicionada a gates |
| `codebridge_search_context` | `query, project, top_k, source_types, path_filter, branch` | Pesquisa indexada com proveniência |
| `codebridge_get_context` | Identificadores de chunks autorizados e projeto | Recupera contexto indexado, não lê paths arbitrários |
| `codebridge_rag_generation_probe` | Sem argumentos | Diagnóstico de geração, declarado no servidor |
| `codebridge_rag_integrity` | Sem argumentos | Diagnóstico de integridade, declarado no servidor |
| `codebridge_rag_queue_bootstrap` | Conferir assinatura do código | Bootstrap da fila incremental; não equivale à publicação |

Os três últimos métodos podem não estar expostos à conexão corrente. Consultas que exigem ferramenta não oferecida pelo cliente não devem ser descritas como executadas.

### Exemplos

```json
{"project":"codebridge","query":"Em qual arquivo o runtime trata o cancelamento?","top_k":5}
```

Chamada: `codebridge_search_context`.

```json
{"project_id":"codebridge","project_root":"C:\\Users\\Matheus\\CodeBridge-MCP-Bridge","scope":"BOTH","paths":["README.md"],"execute":false}
```

Chamada: `codebridge_rag_index`. **Não publica nada**; é um planejamento de elegibilidade de fonte.

## Ferramentas de compatibilidade

Nomes históricos `codebridge_v2_start`, `codebridge_v2_status`, `codebridge_v2_result`, `codebridge_v2_output`, `codebridge_v2_stop`, `codebridge_start` e `codebridge_execution_status` não são o caminho preferido de novas integrações. Utilize `codebridge_exec`, `codebridge_wait` e `codebridge_stop`.

## Como confirmar um contrato

A assinatura real de cada ferramenta está em `author_mcp/mcp_server.py` e na descrição MCP descoberta pelo cliente. Os campos desta referência são um guia funcional, não uma substituição ao schema dinâmico e à política de autorização. Para limites, consulte `codebridge_capabilities`. Para disponibilidade, `codebridge_status`.
