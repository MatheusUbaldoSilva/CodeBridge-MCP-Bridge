# Roadmap — CodeBridge 2.0 MCP Bridge

## Fundação — concluída

- repositório independente do Browser Bridge 1.x;
- runtime local próprio;
- PowerShell 5.1, CMD e SSH persistentes;
- API local autenticada;
- interface própria com xterm.js;
- telemetria Windows e Linux.

## MCP autoral — concluído no caminho local

- protocolo `CBMCP/1`;
- handshake SYN/ACK nos dois sentidos;
- ledger persistente do protocolo;
- MCP streamable HTTP;
- adapter local dedicado;
- status real do CodeBridge;
- execução V2 persistente;
- output incremental por cursor;
- stop por `execution_id`;
- replay idempotente.

## Paridade de terminais — concluída

O executor V2 suporta `POWERSHELL5.1`, `CMD` e `SSH` com o mesmo contrato de start, status, result, output e stop.
## Próximas etapas de estabilização

- autenticação explícita para exposição pública do MCP;
- substituir nomes internos `phase5b/5c/5d/5f` por endpoints V2 canônicos;
- consolidar testes de stress, soak e outputs de múltiplos MB;
- definir retenção/expiração dos ledgers SQLite;
- revisar política de host key da telemetria SSH;
- remover scripts temporários de patch após o próximo checkpoint;
- versionar `app_rewrite`, `author_mcp` e `tests` no Git.

## Critério de aceitação do caminho MCP autoral

Abrir o CodeBridge 2.0 e operar PowerShell 5.1, CMD e SSH exclusivamente pelas ferramentas do MCP autoral, mantendo preparação visível, idempotência, persistência, streaming, cancelamento e auditoria.
