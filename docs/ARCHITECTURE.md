# Arquitetura do CodeBridge

## Visão de componentes

```text
Cliente MCP autorizado (por exemplo, ChatGPT)
           | MCP HTTP via túnel seguro
           v
author_mcp/mcp_server.py (API de ferramentas MCP)
           | protocolo CBMCP/1
           v
author_mcp/adapter_server.py -> app_rewrite/api_server.py
           | localhost, token e runtime
           v
app_rewrite/runtime.py (BridgeRuntime)
     |                 |                  |
 TerminalManager  ExecutionLedger   RAG local
     |                                   |
 PowerShell / CMD / SSH             SQLite + Qdrant + Jina
```

## Limites de responsabilidade

- **Servidor MCP:** expõe ferramentas, valida parâmetros, encapsula erros e formata respostas. Implementação em `author_mcp/mcp_server.py`.
- **Adapter e API local:** encaminham pedidos para o runtime sob controle de acesso. A API do aplicativo usa endereço de loopback por padrão.
- **Runtime:** gerencia a execução, estados, preparação, espera, cancelamento, identificação dos pedidos e snapshots em `app_rewrite/runtime.py`.
- **Terminais:** `TerminalManager` coordena sessões reais Windows e SSH; a interface Qt apenas mostra eventos e interage com elas.
- **RAG:** serviço separado de descoberta de informação. Respostas do RAG não substituem o sistema de arquivos nem a versão Git atual.
- **Desktop:** interface PySide6, gerenciador MCP, túnel e telemetria em `app_rewrite/`.

## Transporte e estados

O protocolo `CBMCP/1` identifica requisições e respostas e possui confirmações de recebimento. A instância observada utiliza servidor MCP em `127.0.0.1:8765/mcp` e adapter local em `127.0.0.1:8766`, porém configurações e portas podem variar. Essas portas não devem ser expostas diretamente na rede.

Há processos locais supervisionados pelo desktop em `author_mcp_manager.py` e `secure_tunnel_manager.py`. O código usa controle de instância única em Windows e canais IPC internos. A disponibilidade de um terminal deve ser consultada, não presumida.

## Interfaces principais

- [MCP_TOOLS.md](MCP_TOOLS.md): entradas externas.
- [EXECUTOR.md](EXECUTOR.md): ciclo de execução e estados.
- [RAG_INTERNALS.md](RAG_INTERNALS.md): organização de armazenamento e consulta.
- [SECURITY.md](SECURITY.md): fronteiras de confiança.
- [STORAGE.md](STORAGE.md): dados persistidos.