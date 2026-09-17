# CodeBridge 2.0 — MCP Bridge

Status: **migração interna para MCP autoral concluída**

O CodeBridge 2.0 usa um MCP próprio como único caminho oficial entre ChatGPT e o runtime local.

## Arquitetura oficial

```text
ChatGPT
   ↓ MCP streamable HTTP
CodeBridge MCP Autoral
   ↓ CBMCP/1
Adapter local
   ↓ API local autenticada
CodeBridge 2.0 Runtime
   ↓
Autoridade única de terminal
   ↓
PowerShell 5.1 | CMD | SSH
   ↓
Execution Ledger / output persistente
   ↑
MCP Autoral
   ↑
ChatGPT
```
## Garantias do caminho atual

- `CBMCP/1` com `REQUEST_SYN → REQUEST_ACK` e `RESPONSE_SYN → RESPONSE_ACK`;
- idempotência por `request_id` e hash SHA-256 do payload;
- ledger SQLite persistente para protocolo e execuções;
- `execution_id` próprio para cada execução;
- PowerShell 5.1, CMD e SSH no mesmo executor V2;
- comando preparado no terminal real antes do Enter;
- resultado final persistido;
- saída incremental append-only por cursor;
- replay sem novo Enter;
- stop direcionado por `execution_id`;
- recuperação de execução incompleta após restart;
- interface local com terminais reais e telemetria;
- ao iniciar, o runtime sobe automaticamente o adapter local `127.0.0.1:8766` e o MCP `127.0.0.1:8765/mcp`;
- no encerramento normal, o runtime encerra somente os processos MCP que ele próprio iniciou.

A ativação automática atual é **somente local**. A exposição externa é uma camada separada e não é iniciada pelo runtime.

Para integração remota existe uma segunda instância MCP em `127.0.0.1:8767/mcp`, exposta por túnel HTTPS e protegida por Bearer token. O token é armazenado no Windows Credential Manager (`CodeBridge-MCP-Bridge:MCP-Public`) e não é gravado no repositório nem no arquivo de estado. `author_mcp/public_stack.py` inicia, consulta e encerra somente os processos públicos que ele próprio criou.

## Ferramentas MCP principais

`codebridge_status`, `codebridge_v2_start`, `codebridge_v2_status`, `codebridge_v2_result`, `codebridge_v2_output` e `codebridge_v2_stop`.

O Browser Bridge 1.x permanece um projeto separado. O CodeBridge 2.0 não depende da extensão Chrome, DOM do ChatGPT, digitação simulada ou protocolo textual `@CODEBRIDGE`.
