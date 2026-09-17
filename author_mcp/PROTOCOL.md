# CodeBridge MCP Autoral — contrato CBMCP/1

Versão do protocolo: `CBMCP/1`.

O MCP autoral é o transporte oficial do CodeBridge 2.0. O shell nunca é executado diretamente pelo servidor MCP: toda operação passa pelo adapter e pelo runtime local do CodeBridge.

## Handshake obrigatório

Toda operação usa `request_id` e SHA-256 do payload JSON canônico.

Fluxo do pedido:

1. MCP → adapter: `REQUEST_SYN`.
2. Adapter persiste e valida o pedido antes do efeito colateral.
3. Adapter → MCP: `REQUEST_ACK` com `request_id` e `request_hash`.
4. Mesmo `request_id` + mesmo payload é replay idempotente.
5. Mesmo `request_id` + payload diferente é conflito.

Fluxo da resposta:

1. Adapter prepara o resultado e cria `response_id` + `response_hash`.
2. Adapter → MCP: `RESPONSE_SYN`.
3. MCP valida identidade e hash da resposta.
4. MCP → adapter: `RESPONSE_ACK`.
5. A troca só termina após o `RESPONSE_ACK` persistido.
## Executor V2

Ferramentas principais:

- `codebridge_status`;
- `codebridge_v2_start(target, command)`;
- `codebridge_v2_status(execution_id)`;
- `codebridge_v2_result(execution_id)`;
- `codebridge_v2_output(execution_id, cursor, max_chars)`;
- `codebridge_v2_stop(execution_id)`.

Destinos suportados: `POWERSHELL5.1`, `CMD` e `SSH`.

Estados persistentes: `CREATED`, `RUNNING`, `FINISHED`, `FAILED`, `CANCELLED`, `INTERRUPTED`.

## Invariantes

- `request_id` não pode representar dois payloads diferentes;
- `execution_id` identifica uma única execução;
- output publicado por cursor é append-only;
- stop atua somente sobre a execução identificada;
- restart não repete automaticamente uma mutação incerta;
- o terminal real continua sendo a autoridade de execução.
