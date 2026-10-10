# RAG-017 — Origem confirmada da divergência MCP (2026-10-10)

Comparação somente leitura na máquina MatheusPC entre o servidor MCP instalado e o repositório experimental.

- Instalado: `C:\Users\Matheus\AppData\Local\Programs\CodeBridge\author_mcp\mcp_server.py`, 37.799 bytes, modificado 2026-10-06 00:25:05; SHA-256 `2C14C93032957FDA32D9215AB4F36CE7974FB599F2563EDAD1AA9B5FEE749607`. Não contém a definição `name="codebridge_rag_status"`.
- Repositório: `C:\Users\Matheus\CodeBridge-MCP-Bridge\author_mcp\mcp_server.py`, 46.784 bytes, modificado 2026-10-07 21:16:51; SHA-256 `72CCDAFF8B7C53A5B1AA29A7D3BB4AD4DB9C6776B4F1FF7869040FC8D55A7D2D`. Contém `codebridge_rag_status`.
- O gerenciador `app_rewrite/author_mcp_manager.py` inicia `mcp_server.py` relativo a `self.author_dir`. Em runtime, a porta 8765 está atribuída ao processo Python PID 12776, filho do pythonw PID 10132, iniciado em 2026-10-08. Um cliente MCP local listou 9 ferramentas e nenhuma RAG.
- O CodeBridge autoral informou READY, 2.0.11-prealpha, API online. Isso demonstra comunicação, mas não atualidade do arquivo servido.

**Conclusão:** existe uma cópia instalada mais antiga e divergente do código do repositório, suficiente para explicar a ausência de ferramentas RAG no catálogo instalado. Não foi efetuada substituição, reinicialização ou ativação experimental. O processo atual deve ser identificado e atualizado por pipeline normal do instalador, com backup, verificação da versão/ambiente Python e rollback, seguido de teste do catálogo MCP. Não copiar o script isoladamente enquanto não forem verificadas dependências e compatibilidade com o pacote instalado.

A alteração preexistente em `benchmarks/rag017_code_only_extended_smoke.json` permanece fora de commits. Build dual anotada preservada. RAG-017-J continua BLOCKED; holdout independente permanece pendente.
