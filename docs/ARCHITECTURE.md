# Arquitetura — CodeBridge 2.0 MCP Bridge

## Princípio central

O MCP autoral é o único transporte oficial entre ChatGPT e o CodeBridge 2.0. A autoridade de execução permanece dentro do runtime local.

## Fluxo

1. ChatGPT chama uma ferramenta do MCP autoral.
2. O MCP cria um `REQUEST_SYN` CBMCP/1.
3. O adapter persiste e confirma o pedido com `REQUEST_ACK`.
4. O adapter chama a API local autenticada do CodeBridge.
5. O runtime valida alvo, identidade e disponibilidade do terminal.
6. O comando é preparado no terminal real.
7. O executor V2 registra `execution_id`, estado e saída incremental.
8. PowerShell 5.1, CMD ou SSH executa o comando.
9. O resultado é persistido localmente.
10. O adapter cria `RESPONSE_SYN` e o MCP confirma com `RESPONSE_ACK`.

## Autoridade de terminal

`TerminalManager.prepare()` possui a trava lógica comum para impedir que dois caminhos de automação preparem comandos simultaneamente.

Os destinos canônicos são `POWERSHELL5.1`, `CMD` e `SSH`.
## Persistência

- `author_mcp_protocol.db`: handshake CBMCP/1 e deduplicação;
- `executions_v2.db`: identidade, estado e resultado das execuções;
- `execution_output_chunks`: saída incremental append-only por cursor;
- `jobs.db`: fila local tradicional da interface.

## Invariantes

- o MCP não executa shell diretamente;
- nenhum retry pode executar novamente uma mutação já associada ao mesmo `request_id`;
- o comando aparece no terminal real antes do Enter;
- resultados só concluem o handshake após `RESPONSE_ACK`;
- restart transforma execução V2 incompleta de runtime anterior em `INTERRUPTED`;
- stop por `execution_id` só atua sobre a execução correspondente;
- PowerShell 5.1, CMD e SSH usam o mesmo contrato V2 de start/status/result/output/stop.

## Ciclo de vida do MCP autoral

`BridgeRuntime.start()` sobe a stack local do MCP autoral depois que a API local e o `runtime.json` já estão disponíveis.

O `AuthorMCPManager` inicia somente:
- adapter local em `127.0.0.1:8766`;
- servidor MCP local em `127.0.0.1:8765/mcp`.

Se uma stack completa já estiver online, o runtime apenas a detecta e não assume propriedade. Se apenas uma das portas estiver ocupada, o início automático é bloqueado como estado degradado para evitar colisão.

`BridgeRuntime.stop()` encerra somente processos iniciados pelo próprio `AuthorMCPManager`. Túnel público/ngrok não faz parte deste lifecycle local.

## Acesso remoto autenticado

O acesso remoto usa uma segunda instância do mesmo MCP em `127.0.0.1:8767/mcp`, mantendo `8765` exclusivamente local. O túnel HTTPS encaminha apenas para `8767`.

A instância pública exige `Authorization: Bearer <token>`. O segredo é mantido no Windows Credential Manager sob `CodeBridge-MCP-Bridge:MCP-Public`; arquivos de estado registram somente fingerprint SHA-256 reduzido, URL e PIDs. Requisições sem credencial válida recebem HTTP 401 antes de alcançar o protocolo MCP.

`author_mcp/public_stack.py` não encerra processos genéricos: no stop ele atua somente nos PIDs que registrou e valida a linha de comando antes de finalizar.

## Interface

A interface usa PySide6 + QWebEngineView + xterm.js para exibir os terminais persistentes. O estado do MCP autoral é obtido pelo health do adapter e pela porta do servidor MCP.
