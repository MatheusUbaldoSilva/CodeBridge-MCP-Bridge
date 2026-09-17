# CodeBridge MCP Autoral — status da migração

Atualizado em 2026-09-17.

## Estado atual

Status: **MIGRAÇÃO INTERNA CONCLUÍDA PARA O MCP AUTORAL**.

O CodeBridge 2.0 não possui mais dependência ativa do agente ou pacote de MCP de terceiros usado durante a transição. O MCP oficial do projeto é `author_mcp`.

Fluxo atual:

`ChatGPT → MCP autoral → CBMCP/1 → adapter → API local → CodeBridge Runtime → TerminalManager → PowerShell/CMD/SSH`.

## Protocolo

Validado:
- `REQUEST_SYN → REQUEST_ACK`;
- `RESPONSE_SYN → RESPONSE_ACK`;
- SHA-256 do payload canônico;
- idempotência por `request_id`;
- conflito em reutilização com payload diferente;
- persistência SQLite do handshake;
- replay preservado após reabertura do ledger.
## Executor V2

O executor persistente V2 suporta os três destinos canônicos:

- `POWERSHELL5.1`;
- `CMD`;
- `SSH`.

Recursos validados:
- start assíncrono com `execution_id`;
- status e resultado persistentes;
- output incremental append-only por cursor;
- replay do mesmo pedido sem novo Enter;
- stop por `execution_id`;
- estado `CANCELLED` com efeito colateral interrompido;
- recuperação de execução incompleta como `INTERRUPTED` após restart.

## Evidência de regressão desta migração

- protocolo em memória: 4/4 testes;
- ledger persistente CBMCP/1: 2/2 testes;
- execution ledger: 7/7 testes;
- V2 local PowerShell/CMD/SSH: PASS;
- cancelamento com efeito colateral PowerShell/CMD/SSH: PASS;
- MCP autoral local PowerShell/CMD/SSH + stop: PASS.
## Pendências que não bloqueiam a migração interna

- revalidar a exposição pública após definir autenticação própria;
- trocar nomes internos de endpoints de fase por rotas V2 canônicas;
- executar stress/soak e outputs de múltiplos MB;
- definir política de retenção dos bancos SQLite;
- versionar os fontes atuais no Git.

Essas pendências são de estabilização e distribuição. O caminho local funcional já usa exclusivamente o MCP autoral do CodeBridge.
