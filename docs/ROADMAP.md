# Roadmap inicial — CodeBridge 2.0 MCP Bridge

## Fase 0 — Fundação

- repositório novo e independente;
- documentação de arquitetura e contratos;
- identidade própria do protocolo MCP/IPC;
- nenhum código da extensão do Browser Bridge.

## Fase 1 — Núcleo local

- status estruturado;
- execução PowerShell 5.1;
- execução CMD;
- execução SSH;
- fila e aprovação;
- resultado correlacionado;
- confirmação de consumo;
- cancel e stop.

## Fase 2 — Integração MCP

- adaptador local dedicado;
- operações estruturadas `status`, `run`, `cancel`, `stop`, `result` e `history`;
- correlação por sessão/conversa sem depender de aba do navegador;
- tratamento de timeout, reconexão e idempotência.
## Fase 3 — Operação integrada

- Remote Desktop Commander inicia com o CodeBridge 2.0;
- indicador visual MCP conectado/desconectado;
- encerramento controlado do agente;
- testes de erro, cancelamento, stop e perda de conexão;
- testes com saída grande e caracteres especiais;
- medição de latência por destino.

## Critério de aceitação

Abrir o CodeBridge 2.0, entrar no ChatGPT e executar tarefas em PowerShell, CMD e SSH sem extensão de navegador, sem protocolo textual visível e sem intervenção manual no terminal, preservando aprovação, histórico, cancelamento e auditoria.
